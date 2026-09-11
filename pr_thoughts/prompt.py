"""PR row -> prompt asking an LLM to write the developer's thoughts behind a real PR.

The LLM writes only prose (task description, per-commit reasoning, summary).
The real code (base files, diffs) is spliced back in by assemble.py.
"""
import hashlib
import random
import re

MAX_TOUCHED_FILES = 15        # skip PRs touching this many files or more
MAX_FILE_LINES = 800          # longer base files show only the regions around the diff
MAX_DIFF_LINES_PER_FILE = 200
HUNK_CONTEXT_LINES = 20

BUMP_TERMS = ("bump", "upgrade dependency", "upgrade dependencies", "update dependency",
              "update dependencies", "chore(deps)", "renovate", "dependabot")


def should_process(row):
    pr, code = row["pull_request"], row["code"]
    text = f"{pr['title'] or ''}\n{pr['body'] or ''}".lower()
    if any(term in text for term in BUMP_TERMS):              # dependency bumps
        return False
    if (code["debug"] or {}).get("git_error") is not None:     # broken code data
        return False
    return len(code["touched_files"] or []) < MAX_TOUCHED_FILES


# ---------------------------------------------------------------------------
# Diversity knobs (sampled once per PR, seeded by the PR id)
# ---------------------------------------------------------------------------

def sample_knobs(rng):
    k = {}
    k["detail_level"] = rng.choices(["minimal", "moderate", "detailed"], weights=[0.2, 0.5, 0.3])[0]
    k["style"] = rng.choices(["github_issue", "direct_instruction", "conversational", "spec"],
                             weights=[0.25, 0.35, 0.25, 0.15])[0]
    k["include_plan"] = rng.random() < 0.35
    k["mention_files"] = rng.random() < 0.6
    k["show_directory_tree"] = rng.choices(["always", "never", "auto"], weights=[0.15, 0.40, 0.45])[0]
    k["directory_tree_format"] = rng.choices(["tree", "flat", "indented"], weights=[0.10, 0.75, 0.15])[0]
    k["show_line_numbers"] = rng.random() < 0.3
    k["diff_format"] = rng.choices(["unified", "search_replace", "full_file"], weights=[0.65, 0.25, 0.10])[0]
    k["reasoning_granularity"] = rng.choices(["per_commit", "per_file"], weights=[0.5, 0.5])[0]
    k["final_output_format"] = rng.choices(["diff_only", "full_files", "both"], weights=[0.60, 0.25, 0.15])[0]

    if k["detail_level"] == "minimal":
        if k["mention_files"]:
            k["mention_files"] = rng.random() < 0.3
        k["include_plan"] = False
    if k["diff_format"] == "full_file":
        k["final_output_format"] = "diff_only"
    if k["diff_format"] != "unified":
        k["show_line_numbers"] = False
    return k


# ---------------------------------------------------------------------------
# Truncation helpers (also used by assemble.py)
# ---------------------------------------------------------------------------

def hunk_ranges(diff, path):
    """(start, end) line ranges in the original file touched by `diff` for `path`."""
    path_re = re.compile(r"(^|[ /])" + re.escape(path) + r"$")
    ranges, in_file = [], False
    for line in diff.splitlines():
        if line.startswith("--- ") or line.startswith("+++ "):
            in_file = bool(path_re.search(line))
        if in_file and line.startswith("@@"):
            m = re.search(r"@@ -(\d+)(?:,(\d+))?", line)
            if m:
                start = int(m.group(1))
                ranges.append((start, start + int(m.group(2) or 1)))
    return ranges


def smart_truncate(content, path, diff, max_lines):
    """Keep only the lines around the diff hunks (head + tail as a fallback)."""
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content, False

    keep = set()
    for start, end in hunk_ranges(diff, path):
        keep.update(range(max(0, start - 1 - HUNK_CONTEXT_LINES), min(len(lines), end + HUNK_CONTEXT_LINES)))
    if keep and len(keep) <= max_lines:
        out, prev = [], -1
        for i in sorted(keep):
            if i > prev + 1:
                out.append(f"... [lines {prev + 2 if prev >= 0 else 1}–{i} omitted] ...")
            out.append(lines[i])
            prev = i
        if prev < len(lines) - 1:
            out.append(f"... [lines {prev + 2}–{len(lines)} omitted] ...")
        return "\n".join(out), True

    half = max_lines // 2
    return "\n".join(lines[:half] + [f"... [{len(lines) - max_lines} lines omitted] ..."] + lines[-half:]), True


def truncate_diff(diff, max_lines):
    """Cap every file's chunk of a multi-file diff at `max_lines` lines."""
    chunks = [[]]
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            chunks.append([])
        chunks[-1].append(line)
    if not chunks[0]:
        chunks.pop(0)
    if not chunks:
        return diff, False

    out, truncated = [], False
    for chunk in chunks:
        if len(chunk) > max_lines:
            chunk = chunk[:max_lines] + [f"... [{len(chunk) - max_lines} lines omitted] ..."]
            truncated = True
        out.append("\n".join(chunk))
    return "\n".join(out), truncated


def files_in_patch(patch):
    return re.findall(r"^diff --git a/.+ b/(.+)$", patch, re.MULTILINE)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

INSTRUCTIONS = """<instructions>
You are helping create a training document that simulates an agentic coding session.
You will be given real PR metadata, code diffs, and file contents from a GitHub repository.

Your job is to SYNTHESIZE only three types of text:
1. **Task description** — a rewritten version of the PR's purpose.
2. **Commit reasoning** — for each commit, a developer's inner monologue explaining
   what they are about to change and why, BEFORE each edit.
3. **Final summary** — a concise wrap-up of all changes made.

IMPORTANT:
- Do NOT copy the PR title or body verbatim. Rewrite the intent in your own words.
- The reasoning should sound like a real developer thinking aloud, not a code review.
- Reference specific functions, classes, variable names from the actual diffs.
- Keep reasoning grounded in what the diff actually changes. Do not invent extra changes.
- Do NOT reference reviewers, review comments, or code review feedback. The reasoning
  should read as a developer's own thinking, not a response to review.
- Do NOT mention "this PR", "the PR", "pull request", or "this diff". Write as if
  the developer is working on a task, not describing a PR.
- Do NOT use markdown formatting (no **, no ##, no bullet points) in reasoning blocks.
  Reasoning should be plain prose — a developer's inner monologue.
- Vary the phrasing of reasoning blocks. Do NOT start every block with "I need to"
  or "Looking at the". Use diverse openings: describe what you notice in the code,
  state the problem directly, explain the approach, think about edge cases, etc.
- Do NOT reproduce any code, diffs, or file contents in your output. Only write prose.
</instructions>"""

STYLE_INSTRUCTIONS = {
    "github_issue": (
        "Write the task description as a GitHub issue. Use a clear title line "
        "followed by a description body. You may use markdown formatting."
    ),
    "direct_instruction": (
        "Write the task description as a direct instruction to a developer. "
        "Be imperative: 'Refactor X to do Y', 'Update the tests to ...', etc."
    ),
    "conversational": (
        "Write the task description in a casual, conversational tone, as if "
        "a developer is asking a colleague for help in a chat. "
        "Use first person, e.g. 'Hey, I need to update these tests because...'"
    ),
    "spec": (
        "Write the task description as a formal technical specification. "
        "Use precise language and state requirements clearly."
    ),
}

DETAIL_INSTRUCTIONS = {
    "minimal": (
        "Keep the task description SHORT — 1 to 3 sentences maximum. "
        "Just state what needs to be done."
    ),
    "moderate": (
        "Write a moderate-length task description — a short paragraph. "
        "Include enough context to understand *why* the change is needed."
    ),
    "detailed": (
        "Write a detailed task description — multiple paragraphs if needed. "
        "Explain background/motivation, what needs to change, and why."
    ),
}


def pr_context(row):
    pr, code = row["pull_request"], row["code"]
    lines = ["<pr_context>", f"Repository: {code['repo_full_name']}"]
    repo_description = (pr["base"]["repo"]["description"] or "").strip()
    if repo_description:
        lines.append(f"Repository description: {repo_description}")
    lines.append(f"PR title: {pr['title']}")
    if pr["body"]:
        lines.append(f"PR body:\n{pr['body']}")
    labels = [l["name"] for l in pr["labels"] or [] if l["name"]]
    if labels:
        lines.append(f"Labels: {', '.join(labels)}")
    lines.append(f"Files changed: {pr['changed_files']}")
    lines.append(f"Additions: +{pr['additions']}, Deletions: -{pr['deletions']}")

    comments = [ev[key]["body"].strip() for ev in row["events"] or [] for key in ("comment", "review")
                if ev[key] and ev[key]["body"] and ev[key]["body"].strip()]
    if comments:
        lines.append("\nReview discussion (use as background context only — do NOT "
                     "reference reviewers or review feedback in your output):")
        lines += [f"  [{i}] {c}" for i, c in enumerate(comments, 1)]
    lines.append("</pr_context>")
    return "\n".join(lines)


def base_files_context(code):
    base_files = code["base_files_at_base"] or []
    if not base_files:
        return "<base_files>\n(all files are newly created)\n</base_files>"
    lines = ["<base_files>", "File contents BEFORE changes:"]
    for bf in base_files:
        text, truncated = smart_truncate(bf["content"] or "", bf["path"], code["compare_diff"] or "", MAX_FILE_LINES)
        lines.append(f"\n--- {bf['path']}{' (truncated to diff-relevant regions)' if truncated else ''} ---")
        lines.append(text)
    lines.append("</base_files>")
    return "\n".join(lines)


def commits_context(commits):
    lines = ["<commits>", f"Total commits: {len(commits)}"]
    for i, commit in enumerate(commits, 1):
        subject = commit["subject"] or "(no subject)"
        patch = commit["patch"] or ""
        if patch.startswith(subject):
            patch = patch[len(subject):].lstrip("\n")
        patch, _ = truncate_diff(patch, MAX_DIFF_LINES_PER_FILE)
        lines += [f'\n<commit index="{i}" sha="{commit["sha"][:8]}">', f"Subject: {subject}", f"Diff:\n{patch}", "</commit>"]
    lines.append("</commits>")
    return "\n".join(lines)


def output_instructions(knobs, commits, touched_files):
    plan = ("The task description MUST end with a plan section outlining the "
            "steps/files to modify. Write it naturally (e.g. 'Plan: 1. ...')."
            if knobs["include_plan"] else
            "Do NOT include a step-by-step plan. Just describe the goal/problem.")
    files = (f"Reference the specific files to change: {', '.join(touched_files)}."
             if knobs["mention_files"] else
             "Do NOT mention specific filenames. Describe at a higher level.")

    if knobs["reasoning_granularity"] == "per_commit":
        reasoning = ("Write ONE <reasoning> block per commit. If a commit touches "
                     "multiple files, cover all of them in a single reasoning block.")
        blocks = [f'<reasoning commit="{i}">\n(developer\'s reasoning before commit {i})\n</reasoning>'
                  for i in range(1, len(commits) + 1)]
    else:
        reasoning = ("Write a SEPARATE <reasoning> block for each FILE changed within "
                     "each commit. Use the file attribute to indicate which file, e.g. "
                     'commit="1" file="path/to/file.py". This should read as a '
                     "developer reasoning about one file at a time before editing it.")
        blocks = []
        for i, commit in enumerate(commits, 1):
            paths = files_in_patch(commit["patch"] or "")
            if not paths:
                blocks.append(f'<reasoning commit="{i}">\n(developer\'s reasoning before commit {i})\n</reasoning>')
            blocks += [f'<reasoning commit="{i}" file="{p}">\n(developer\'s reasoning before editing {p})\n</reasoning>'
                       for p in paths]

    # What assembly.py will add around the prose (told to the LLM for awareness).
    parts = ["a repository directory tree"] if knobs["show_directory_tree"] != "never" else []
    parts.append(f"code diffs in {knobs['diff_format']} format")
    if knobs["diff_format"] != "full_file":
        parts.append(f"a final {knobs['final_output_format'].replace('_', ' ')} section")
    context = ("The final training document will also include " + ", ".join(parts)
               + " — these are added automatically, you don't need to produce them.")

    template = "\n\n".join(blocks)
    return f"""<output_instructions>
You are outputting ONLY synthesized prose — no code, no diffs, no file contents.
The code will be spliced in by a separate assembly step.

TASK DESCRIPTION:
{STYLE_INSTRUCTIONS[knobs["style"]]}
{DETAIL_INSTRUCTIONS[knobs["detail_level"]]}
{plan}
{files}

REASONING:
{reasoning}
Each reasoning block should explain what the developer is about to do and why,
referencing specific code elements visible in the diffs. Think of it as a
developer's internal monologue before making an edit.
- Use plain prose only. No markdown formatting, no bold, no headers, no lists.
- Vary your phrasing across blocks. Don't start every block the same way.

CONTEXT: {context}

OUTPUT FORMAT (output ONLY this XML, nothing else):

<task_description>
(your synthesized task description)
</task_description>

{template}

<summary>
(2-5 sentence summary of all changes)
</summary>
</output_instructions>"""


def build_prompt(row):
    """Returns (prompt, knobs)."""
    seed = int(hashlib.md5(f"{row['repo_id']}_{row['pr_number']}".encode()).hexdigest()[:8], 16)
    knobs = sample_knobs(random.Random(seed))

    code = row["code"]
    commits = code["commits"] or []
    sections = [INSTRUCTIONS, pr_context(row), base_files_context(code), commits_context(commits)]
    if code["compare_diff"]:
        diff, truncated = truncate_diff(code["compare_diff"], MAX_DIFF_LINES_PER_FILE)
        sections.append(f"<final_combined_diff{' (truncated)' if truncated else ''}>\n{diff}\n</final_combined_diff>")
    sections.append(output_instructions(knobs, commits, code["touched_files"] or []))
    return "\n\n".join(sections), knobs
