"""LLM prose + real PR code -> final training document.

The task description, the developer's reasoning before each commit and the
summary come from the LLM; the repository tree, base files and diffs are the
real ones from the PR. How the code is rendered is decided by knobs drawn here.
"""
import hashlib
import json
import os
import random
import re
from collections import defaultdict

import pyarrow.parquet as pq
from transformers import AutoTokenizer

import connectors as C
from prompt import smart_truncate

TOKENIZER = "IFM/K2-Horizon-375B-A23B"   # only used to measure document length
TREE_MAX_FILES = 200
FULL_FILE_MAX_BASE_CHARS = 30_000
EMPTY_CONNECTOR_PROB = 0.75
RETRY_TOKENS = 128_000                   # longer documents are re-rendered more compactly
MAX_TOKENS = 512_000                     # longer documents are dropped
LONG_CONTEXT_BOOST_PROB = 0.80
TRUNCATION_LADDER = ["none", "1000_line", "500_line", "350_line", "200_line", "100_line"]


def pr_rng(row, salt):
    return random.Random(int(hashlib.md5(f"{row['repo_id']}_{row['pr_number']}_{salt}".encode()).hexdigest()[:8], 16))


# ---------------------------------------------------------------------------
# Parse the LLM output
# ---------------------------------------------------------------------------

def extract_tag(text, tag):
    m = re.search(rf"^\s*<{tag}>\s*\n(.*?)\n\s*</{tag}>", text, re.DOTALL | re.MULTILINE)
    if not m:
        m = re.search(rf"^\s*<{tag}>(.*?)</{tag}>", text, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else None


def parse_generation(generation):
    if "</think>" not in generation:            # ran out of tokens while thinking
        return None
    answer = generation.split("</think>", 1)[1]  # the thinking often holds drafts of the answer; never parse it
    task, summary = extract_tag(answer, "task_description"), extract_tag(answer, "summary")
    reasoning = []
    for m in re.finditer(r'<reasoning\s+commit="([^"]+)"(?:\s+file="([^"]*)")?\s*>(.*?)</reasoning>', answer, re.DOTALL):
        commit = m.group(1).split(",")[0].strip()
        if commit.isdigit():
            reasoning.append({"commit": int(commit), "file": m.group(2), "text": m.group(3).strip()})
    if not task or not summary or not reasoning:
        return None
    return {"task_description": task, "reasoning": reasoning, "summary": summary}


# ---------------------------------------------------------------------------
# Rendering knobs
# ---------------------------------------------------------------------------

def sample_render_knobs(rng, knobs, row):
    # These were fixed at generation time (the LLM wrote its reasoning for them).
    k = {key: knobs[key] for key in ("show_directory_tree", "directory_tree_format", "show_line_numbers", "reasoning_granularity")}
    # These are drawn now (the prompt only mentioned diff/final formats as context).
    k["diff_format"] = rng.choices(["unified", "search_replace", "full_file"], weights=[0.90, 0.08, 0.02])[0]
    k["final_output_format"] = rng.choices(["diff_only", "full_files", "both"], weights=[0.79, 0.20, 0.01])[0]
    k["line_number_style"] = rng.choices(["colon", "pipe"], weights=[0.70, 0.30])[0]
    k["base_file_format"] = rng.choices(["dashes", "xml"], weights=[0.85, 0.15])[0]
    k["base_file_truncation"] = rng.choices(["none", "1000_line", "500_line", "200_line"], weights=[0.40, 0.25, 0.20, 0.15])[0]
    k["base_file_layout"] = rng.choices(["upfront", "interleaved"], weights=[0.70, 0.30])[0]
    k["repo_mention"] = rng.choices(["prefix", "suffix", "none"], weights=[0.35, 0.35, 0.30])[0]
    k["markdown_fence"] = rng.random() < 0.10

    biggest_base = max([len(bf["content"] or "") for bf in row["code"]["base_files_at_base"] or []], default=0)
    if k["diff_format"] == "full_file" and biggest_base > FULL_FILE_MAX_BASE_CHARS:
        k["diff_format"] = "unified"
    if k["diff_format"] == "full_file":
        k["final_output_format"] = "diff_only"
    if k["final_output_format"] != "diff_only":   # post-change files are derived from the untruncated base
        k["base_file_truncation"] = "none"
    if k["diff_format"] != "unified":
        k["show_line_numbers"] = False
    if k["base_file_format"] == "xml" and k["show_line_numbers"]:
        k["line_number_style"] = "colon"
    if k["base_file_format"] == "xml" or k["show_line_numbers"]:
        k["markdown_fence"] = False
    return k


def harden_steps(k):
    """More and more compact knobs: first drop full-file output, then truncate base files harder."""
    if k["diff_format"] == "full_file" or k["final_output_format"] != "diff_only":
        k = {**k, "diff_format": "unified" if k["diff_format"] == "full_file" else k["diff_format"],
             "final_output_format": "diff_only"}
        yield k
    for level in TRUNCATION_LADDER[TRUNCATION_LADDER.index(k["base_file_truncation"]) + 1:]:
        k = {**k, "base_file_truncation": level}
        yield k


# ---------------------------------------------------------------------------
# Code rendering helpers
# ---------------------------------------------------------------------------

def split_patch(patch):
    """{path: that file's diff}; anything that is not a per-file diff goes under '__other__'."""
    out = {}
    for part in re.split(r"(?=^diff --git )", patch, flags=re.MULTILINE):
        part = part.strip()
        if part:
            m = re.match(r"^diff --git a/.+ b/(.+)$", part, re.MULTILINE)
            out[m.group(1) if m else "__other__"] = part
    return out


def apply_diff(content, diff):
    hunks = []
    for line in diff.split("\n"):
        m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if m:
            hunks.append({"start": int(m.group(1)), "count": int(m.group(2)) if m.group(2) else 1, "new": []})
        elif hunks and (line.startswith("+") or line.startswith(" ")):
            hunks[-1]["new"].append(line[1:])
    lines = content.split("\n")
    for h in reversed(hunks):
        if h["start"] == 0 and h["count"] == 0:        # new file
            lines = h["new"] + (lines if lines != [""] else [])
        else:
            lines[h["start"] - 1:h["start"] - 1 + h["count"]] = h["new"]
    return "\n".join(lines)


def to_search_replace(diff):
    m = re.match(r"^diff --git a/.+ b/(.+)$", diff, re.MULTILINE)
    path = m.group(1) if m else "unknown"
    blocks = []
    for hunk in re.split(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@.*$", diff, flags=re.MULTILINE)[1:]:
        old, new = [], []
        for line in hunk.split("\n"):
            if line.startswith("-"):
                old.append(line[1:])
            elif line.startswith("+"):
                new.append(line[1:])
            elif line.startswith(" "):
                old.append(line[1:])
                new.append(line[1:])
        if old != new:
            blocks.append(f"--- {path}\n<<<<<<< SEARCH\n" + "\n".join(old) + "\n=======\n" + "\n".join(new) + "\n>>>>>>> REPLACE")
    return "\n\n".join(blocks) if blocks else diff


def format_diff(diff, fmt):
    if fmt != "search_replace":
        return diff
    return "\n\n".join(d if path == "__other__" else to_search_replace(d) for path, d in split_patch(diff).items())


def add_line_numbers(content, style):
    lines = content.split("\n")
    if style == "colon":
        return "\n".join(f"{i}: {line}" for i, line in enumerate(lines, 1))
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}} | {line}" for i, line in enumerate(lines, 1))


def md_language(path):
    name = os.path.basename(path).lower()
    if name in ("dockerfile", "makefile"):
        return name
    return C.MD_LANGUAGE.get(os.path.splitext(name)[1].lstrip("."), "")


def file_block(path, content, k):
    if k["base_file_format"] == "xml":
        return f"<path>{path}</path>\n<type>file</type>\n<content>{content}</content>"
    if k["markdown_fence"]:
        return f"--- {path} ---\n```{md_language(path)}\n{content}\n```"
    return f"--- {path} ---\n{content}"


def base_file_block(path, content, k):
    if content is None:
        if k["base_file_format"] == "xml":
            return f"<path>{path}</path>\n<type>file</type>\n<content>(new file)</content>"
        return f"--- {path} ---\n(new file)"
    return file_block(path, add_line_numbers(content, k["line_number_style"]) if k["show_line_numbers"] else content, k)


def truncate_base_files(base_files, compare_diff, level):
    if level == "none":
        return base_files
    max_lines = int(level.split("_")[0])
    return [{**bf, "content": smart_truncate(bf["content"], bf["path"], compare_diff, max_lines)[0]} if bf["content"] else bf
            for bf in base_files]


def truncate_tree(files, touched, max_files):
    """Keep the directories of the touched files (and top-level files), then fill up with the rest."""
    if len(files) <= max_files:
        return files
    relevant = {"/".join(t.split("/")[:i]) for t in touched for i in range(1, len(t.split("/")))}
    kept, other = [], []
    for f in files:
        (kept if "/" not in f or f.rsplit("/", 1)[0] in relevant else other).append(f)
    kept += other[:max(0, max_files - len(kept))]
    return sorted(kept[:max_files])


def format_tree(files, fmt):
    if fmt == "flat":
        return "\n".join(sorted(files))
    if fmt == "indented":
        groups = defaultdict(list)
        for f in sorted(files):
            parts = f.split("/", 1)
            groups["" if len(parts) == 1 else parts[0]].append(parts[-1])
        lines = []
        for group in sorted(groups):
            lines += groups[group] if group == "" else [f"{group}/"] + [f"    {f}" for f in sorted(groups[group])]
        return "\n".join(lines)

    tree = {}
    for f in sorted(files):
        node = tree
        for part in f.split("/"):
            node = node.setdefault(part, {})

    def draw(node, prefix):
        lines, names = [], sorted(node)
        for i, name in enumerate(names):
            last = i == len(names) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}")
            lines += draw(node[name], prefix + ("    " if last else "│   "))
        return lines
    return "\n".join(draw(tree, ""))


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

def commit_per_commit(reasoning, patch, k, file_state):
    """One reasoning block, then the commit's diff."""
    parts = [reasoning[0]["text"]] if reasoning else []
    if k["diff_format"] == "full_file":
        parts += [file_block(p, apply_diff(file_state.get(p, ""), d), k) for p, d in split_patch(patch).items() if p != "__other__"]
    else:
        diff = format_diff(patch, k["diff_format"])
        if diff.strip():
            parts.append(diff)
    return "\n\n".join(parts)


def commit_per_file(reasoning, patch, k, file_state):
    """For each file: its reasoning block, then its diff."""
    by_file = {r["file"]: r["text"] for r in reasoning if r["file"]}
    generic = [r["text"] for r in reasoning if not r["file"]]
    diffs = split_patch(patch)
    if generic and any(p != "__other__" for p in diffs):   # the LLM ignored the per-file format
        return None
    parts = []
    for path, diff in diffs.items():
        if path == "__other__":                            # e.g. a merge-commit diff
            parts += generic[:1] + [diff]
            continue
        if by_file.get(path):
            parts.append(by_file[path])
        if k["diff_format"] == "full_file":
            parts.append(file_block(path, apply_diff(file_state.get(path, ""), diff), k))
        else:
            diff = format_diff(diff, k["diff_format"])
            if diff.strip():
                parts.append(diff)
    return "\n\n".join(parts)


def render(parsed, k, row):
    pr, code = row["pull_request"], row["code"]
    commits = code["commits"] or []
    repo_files = code["repo_files_at_base"] or []
    compare_diff = code["compare_diff"] or ""
    repo_description = (pr["base"]["repo"]["description"] or "").strip()

    reasoning = defaultdict(list)
    for r in parsed["reasoning"]:
        reasoning[r["commit"]].append(r)
    patches = []                                   # commit patches without the repeated subject line
    for i, commit in enumerate(commits, 1):
        subject, patch = commit["subject"] or "", commit["patch"] or ""
        patch = patch[len(subject):].lstrip("\n") if patch.startswith(subject) else patch
        if patch.strip() and i not in reasoning:   # the LLM skipped a commit
            return None
        patches.append(patch)

    base_files = truncate_base_files(code["base_files_at_base"] or [], compare_diff, k["base_file_truncation"])
    rng, used = pr_rng(row, "connectors"), set()

    def connector(pool):
        if rng.random() < EMPTY_CONNECTOR_PROB:
            return ""
        choice = rng.choice([p for p in pool if p not in used] or pool)   # no repeats within a document
        used.add(choice)
        return choice

    def join(conn, text):
        return f"{conn}\n\n{text}" if conn else text

    # 1. Task description, optionally with the repository
    task = parsed["task_description"]
    if repo_description and k["repo_mention"] == "prefix":
        task = f"[{code['repo_full_name']}: {repo_description}]\n\n{task}"
    elif repo_description and k["repo_mention"] == "suffix":
        task = f"{task}\n\n(Repository: {code['repo_full_name']} — {repo_description})"
    sections = [task]

    # 2. Repository tree
    if k["show_directory_tree"] == "always" or (k["show_directory_tree"] == "auto" and len(repo_files) >= 15):
        tree = format_tree(truncate_tree(repo_files, code["touched_files"] or [], TREE_MAX_FILES), k["directory_tree_format"])
        sections.append(join(connector(C.TREE), f"```\n{tree}\n```"))

    # 3. Base files: all up front, or each one right before the first commit touching it
    base_by_path = {bf["path"]: bf for bf in base_files}
    shown = set()
    if base_files and k["base_file_layout"] == "upfront":
        blocks = "\n\n".join(base_file_block(bf["path"], bf["content"], k) for bf in base_files)
        sections.append(join(connector(C.BASE_FILES), blocks))
        shown = set(base_by_path)

    # 4. Commits: reasoning + diff
    file_state = {bf["path"]: bf["content"] or "" for bf in base_files}
    first = True
    for i, patch in enumerate(patches, 1):
        if not patch.strip():
            continue
        parts = []
        if k["base_file_layout"] == "interleaved":
            new = [p for p in split_patch(patch) if p in base_by_path and p not in shown]
            if new:
                blocks = "\n\n".join(base_file_block(p, base_by_path[p]["content"], k) for p in new)
                parts.append(join(connector(C.BASE_FILE_INLINE), blocks))
                shown.update(new)
        conn = connector(C.FIRST_COMMIT if first else C.NEXT_COMMIT)
        first = False
        render_commit = commit_per_file if k["reasoning_granularity"] == "per_file" else commit_per_commit
        body = render_commit(reasoning[i], patch, k, file_state)
        if body is None:
            return None
        parts.append(join(conn, body))
        sections.append("\n\n".join(parts))
        if k["diff_format"] == "full_file" or k["final_output_format"] != "diff_only":
            for path, diff in split_patch(patch).items():
                if path != "__other__":
                    file_state[path] = apply_diff(file_state.get(path, ""), diff)

    # 5. Final result (multi-commit only): combined diff and/or the files after all changes
    if k["diff_format"] != "full_file" and len(commits) > 1:
        conn = connector(C.FINAL_OUTPUT)
        parts = []
        if k["final_output_format"] in ("diff_only", "both"):
            diff = format_diff(compare_diff, k["diff_format"])
            if diff.strip():
                parts.append(diff)
        if k["final_output_format"] in ("full_files", "both"):
            parts += [file_block(bf["path"], file_state.get(bf["path"], bf["content"] or ""), k) for bf in base_files]
        if parts:
            sections.append(join(conn, "\n\n".join(parts)))

    # 6. Summary
    sections.append(join(connector(C.SUMMARY), parsed["summary"]))

    sections = [re.sub(r"\n{3,}", "\n\n", s.strip()) for s in sections if s.strip()]
    return "\n\n".join(sections)


def assemble(row, knobs, generation, tokenizer):
    parsed = parse_generation(generation)
    if parsed is None:
        return None
    rng = pr_rng(row, "knobs")
    k = sample_render_knobs(rng, knobs, row)
    text = render(parsed, k, row)
    if text is None:
        return None
    n = len(tokenizer.encode(text, add_special_tokens=False))

    if n > RETRY_TOKENS:
        for k in harden_steps(k):
            text = render(parsed, k, row)
            n = len(tokenizer.encode(text, add_special_tokens=False))
            if n <= RETRY_TOKENS:
                break

    # Still long: most of the time lean into it and also show the files after the change.
    if RETRY_TOKENS < n <= MAX_TOKENS and k["final_output_format"] == "diff_only" and rng.random() < LONG_CONTEXT_BOOST_PROB:
        boosted = render(parsed, {**k, "final_output_format": "full_files", "base_file_truncation": "none"}, row)
        boosted_n = len(tokenizer.encode(boosted, add_special_tokens=False))
        if boosted_n <= MAX_TOKENS:
            text, n = boosted, boosted_n

    if n >= MAX_TOKENS:
        return None
    return {"text": text, "token_count": n}


if __name__ == "__main__":
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER)
    rows = {(r["repo_id"], r["pr_number"]): r for r in pq.read_table("data/input.parquet").to_pylist()}

    with open("data/generation.jsonl") as fin, open("data/final.jsonl", "w") as fout:
        for line in fin:
            g = json.loads(line)
            doc = assemble(rows[(g["repo_id"], g["pr_number"])], g["knobs"], g["generation"], tokenizer)
            if doc is not None:
                fout.write(json.dumps({"repo_id": g["repo_id"], "pr_number": g["pr_number"], **doc}) + "\n")
