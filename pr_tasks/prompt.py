"""PR row -> prompt asking an LLM to write a standalone coding task that the PR solves."""
import os
import random
import re
from collections import Counter

MAX_TOTAL_FILE_LINES = 5000   # skip PRs whose touched files are too big to orient in
MAX_FILE_LINES = 500          # longer base files show only the regions around the diff
MAX_DIFF_LINES_PER_FILE = 100
HUNK_CONTEXT_LINES = 20
MAX_PR_BODY_CHARS = 5000
MAX_COMMENT_CHARS = 400
MIN_COMMENT_CHARS = 20        # skip "Thanks", "LGTM", "+1", ...
MAX_REPO_FILES = 200


# ---------------------------------------------------------------------------
# Diversity knobs
# ---------------------------------------------------------------------------

EXT_TO_LANG = {
    "py": "Python", "pyi": "Python", "pyx": "Python",
    "js": "JavaScript", "mjs": "JavaScript", "cjs": "JavaScript", "jsx": "JavaScript",
    "ts": "TypeScript", "tsx": "TypeScript",
    "java": "Java", "kt": "Kotlin", "kts": "Kotlin", "scala": "Scala",
    "go": "Go", "rs": "Rust",
    "c": "C", "h": "C", "cpp": "C++", "cc": "C++", "cxx": "C++", "hpp": "C++", "hxx": "C++",
    "cs": "C#", "rb": "Ruby", "erb": "Ruby", "php": "PHP", "swift": "Swift",
    "m": "Objective-C", "mm": "Objective-C", "r": "R", "jl": "Julia", "lua": "Lua",
    "pl": "Perl", "pm": "Perl", "hs": "Haskell", "ex": "Elixir", "exs": "Elixir", "erl": "Erlang",
    "clj": "Clojure", "cljs": "Clojure", "dart": "Dart", "zig": "Zig", "v": "V", "nim": "Nim",
    "ml": "OCaml", "mli": "OCaml", "fs": "F#", "fsx": "F#",
    "sh": "Shell", "bash": "Shell", "zsh": "Shell",
}


def primary_language(repo_files):
    """Most common language by file extension, if it is at least 25% of recognized files."""
    counts = Counter()
    for f in repo_files:
        lang = EXT_TO_LANG.get(os.path.splitext(f)[1].lstrip(".").lower())
        if lang:
            counts[lang] += 1
    if not counts:
        return ""
    lang, n = counts.most_common(1)[0]
    return lang if n / sum(counts.values()) >= 0.25 else ""


def sample_config(row):
    code = row["code"]
    # Bigger PRs lean towards more detailed hints, but every level appears at every size.
    complexity = (min(int(code["commit_count"] or 1), 5) * 0.5
                  + len((code["compare_diff"] or "").splitlines()) / 30
                  + len(code["touched_files"] or []) * 1.5)
    weights = [35, 30, 25, 8, 2] if complexity < 5 else [12, 20, 32, 22, 14] if complexity < 20 else [5, 8, 22, 30, 35]
    hints_level = random.choices(["bare", "concise", "standard", "guided", "detailed"], weights=weights)[0]
    style = random.choice(["instructional", "issue"] if hints_level in ("bare", "concise") else ["instructional", "issue", "spec"])
    persona = "maintainer" if style == "issue" else random.choice(["direct", "maintainer"])
    return {
        "hints_level": hints_level,
        "style": style,
        "persona": persona,
        "scope_framing": random.choices(["targeted", "open"], weights=[0.75, 0.25])[0],
        "include_comments": random.random() < 0.7,
        "primary_language": primary_language(code["repo_files_at_base"] or []),
    }


# ---------------------------------------------------------------------------
# PR context helpers
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


def smart_truncate(content, path, diff):
    """Keep only the lines around the diff hunks (head + tail as a fallback)."""
    lines = content.splitlines()
    if len(lines) <= MAX_FILE_LINES:
        return content, False

    keep = set()
    for start, end in hunk_ranges(diff, path):
        keep.update(range(max(0, start - 1 - HUNK_CONTEXT_LINES), min(len(lines), end + HUNK_CONTEXT_LINES)))
    if keep and len(keep) <= MAX_FILE_LINES:
        out, prev = [], -1
        for i in sorted(keep):
            if i > prev + 1:
                out.append(f"... [lines {prev + 2 if prev >= 0 else 1}–{i} omitted] ...")
            out.append(lines[i])
            prev = i
        if prev < len(lines) - 1:
            out.append(f"... [lines {prev + 2}–{len(lines)} omitted] ...")
        return "\n".join(out), True

    half = MAX_FILE_LINES // 2
    return "\n".join(lines[:half] + [f"... [{len(lines) - MAX_FILE_LINES} lines omitted] ..."] + lines[-half:]), True


def truncate_diff(diff):
    """Cap every file's chunk of a multi-file diff, so no file is silently dropped."""
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
        if len(chunk) > MAX_DIFF_LINES_PER_FILE:
            chunk = chunk[:MAX_DIFF_LINES_PER_FILE] + [f"... [{len(chunk) - MAX_DIFF_LINES_PER_FILE} lines omitted] ..."]
            truncated = True
        out.append("\n".join(chunk))
    return "\n".join(out), truncated


def discussion_comments(events):
    out, seen = [], set()
    for event in events:
        c = event.get("comment")
        if c and isinstance(c.get("body"), str) and len(c["body"].strip()) > MIN_COMMENT_CHARS:
            body = c["body"].strip()
            if body in seen:
                continue
            seen.add(body)
            out.append(body[:MAX_COMMENT_CHARS] + ("…" if len(body) > MAX_COMMENT_CHARS else ""))
    return out


# Build/config files are listed first so the LLM can point at them for setup.
ENV_FILE_PATTERNS = [
    # Python
    r'(^|/)pyproject\.toml$', r'(^|/)setup\.py$', r'(^|/)setup\.cfg$',
    r'(^|/)requirements.*\.txt$', r'(^|/)tox\.ini$',
    r'(^|/)pytest\.ini$', r'(^|/)conftest\.py$',
    # JavaScript / TypeScript
    r'(^|/)package\.json$', r'(^|/)package-lock\.json$',
    r'(^|/)yarn\.lock$', r'(^|/)pnpm-lock\.yaml$',
    r'(^|/)tsconfig.*\.json$',
    r'(^|/)\.eslintrc', r'(^|/)jest\.config\.',
    # Rust
    r'(^|/)Cargo\.toml$', r'(^|/)Cargo\.lock$',
    # Go
    r'(^|/)go\.mod$', r'(^|/)go\.sum$',
    # Java / JVM
    r'(^|/)pom\.xml$', r'(^|/)build\.gradle(\.kts)?$',
    r'(^|/)settings\.gradle(\.kts)?$',
    # Ruby
    r'(^|/)Gemfile$', r'(^|/)Gemfile\.lock$', r'(^|/)Rakefile$',
    # C / C++
    r'(^|/)CMakeLists\.txt$', r'(^|/)meson\.build$',
    r'(^|/)configure\.ac$', r'(^|/)configure\.in$',
    # .NET / C#
    r'(^|/)[^/]*\.csproj$', r'(^|/)[^/]*\.sln$',
    r'(^|/)nuget\.config$',
    # Universal build / CI
    r'(^|/)Makefile$', r'(^|/)justfile$',
    r'(^|/)Dockerfile[^/]*$', r'(^|/)docker-compose[^/]*$',
    r'(^|/)\.github/workflows/[^/]+\.ya?ml$',
    r'(^|/)\.travis\.yml$', r'(^|/)\.circleci/',
]


def sort_repo_files(files):
    """Env/build files first, then by depth, then alphabetically."""
    def key(path):
        for i, pattern in enumerate(ENV_FILE_PATTERNS):
            if re.search(pattern, path, re.IGNORECASE):
                return (0, i, path)
        return (1, path.count("/"), path)
    return sorted(files, key=key)


TEST_FILE_RE = re.compile(
    r'(^|/)(test_|tests?/|spec_|specs?/|__tests__/)'
    r'|'
    r'(Test|_test|_spec|\.test|\.spec)\.[^/]+$',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

STYLE_INTROS = {
    "instructional": (
        "You are synthesizing a standalone coding task from a real GitHub pull request. "
        "The output should read as a direct, actionable assignment for a software developer."
    ),
    "issue": (
        "You are synthesizing a GitHub issue based on a real pull request. "
        "Write it as the issue that would have motivated this work — a bug report, "
        "feature request, or improvement from the perspective of someone encountering the problem."
    ),
    "spec": (
        "You are synthesizing a concise technical specification based on a real GitHub pull request. "
        "Describe the goal, requirements, and acceptance criteria in structured sections."
    ),
}

PERSONA_INSTRUCTIONS = {
    "direct":      "Second-person imperative: 'Implement X', 'Fix Y', 'Ensure Z works correctly'.",
    "maintainer":  "Project maintainer guiding a contributor: 'We need…', 'The goal is to…', 'Please ensure…'.",
}

SCOPE_INSTRUCTIONS = {
    "targeted": "Scope the task to the minimal, focused change the PR represents. Do not invite broader refactoring.",
    "open":     "The developer may restructure related code as needed for a clean solution.",
}

HINTS_INSTRUCTIONS = {
    "bare": """\
Write a short, natural-sounding request — the kind a developer would type into a chat
with a coding assistant or post as a quick message to a colleague.
- 1–3 sentences, casual and direct
- Do NOT include file paths, implementation plans, environment setup, or any structured sections
- Do NOT use markdown formatting, bullet points, or numbered lists
- Just describe the goal or problem naturally""",

    "concise": """\
Include ONLY:
- A concise task title
- A brief description (2–4 sentences) of what needs to be done and why
No guidance on how to implement it. No file paths or setup instructions.""",

    "standard": """\
Include:
- A concise task title
- A description of what needs to be done and why
- Environment setup: identify which repo files the developer should check to figure out how
  to install dependencies and run tests (e.g. pyproject.toml, setup.py, tox.ini, Makefile,
  requirements.txt — look at the repo file listing to see what's actually present)
- A high-level implementation plan (3–6 bullet points, no specific code)""",

    "guided": """\
Include:
- A concise task title
- A description of what needs to be done and why
- Environment setup: identify which repo files the developer should check to figure out how
  to install dependencies and run tests (look at the repo file listing to see what's present)
- A step-by-step implementation plan with reasonable detail
- Testing hints: what to verify, relevant test files to examine, and which config files
  describe how to run the test suite (do NOT fabricate test commands)""",

    "detailed": """\
Include:
- A concise task title
- A description of what needs to be done and why
- Environment setup: identify which repo files the developer should check to figure out how
  to install dependencies and run the test suite (look at the repo file listing to see what's
  actually present)
- A step-by-step implementation plan with reasonable detail
- Testing hints: what to verify, relevant test files to examine, and which config files
  describe how to run the test suite (do NOT fabricate test commands)
- Code structure hints: which files/functions/classes to modify or create, key design decisions""",
}

# Output fields requested at each hints level (all of them are required when parsing).
FIELDS_BY_LEVEL = {
    "bare":     ["description"],
    "concise":  ["title", "description"],
    "standard": ["title", "description", "environment_setup", "implementation_plan"],
    "guided":   ["title", "description", "environment_setup", "implementation_plan",
                 "testing_hints"],
    "detailed": ["title", "description", "environment_setup", "implementation_plan",
                 "testing_hints", "code_hints"],
}

FIELD_DESCRIPTIONS = {
    "title":               "Concise task title, max 15 words",
    "description":         "Full task description. Markdown is fine.",
    "environment_setup":   "Which repo config files to check for install and test instructions "
                           "(e.g. pyproject.toml, Makefile, tox.ini). Only mention files that "
                           "actually appear in the repo file listing. Do NOT guess specific "
                           "install or test commands — just point to the right files.",
    "implementation_plan": "Ordered steps or bullet points describing the approach.",
    "testing_hints":       "What to verify and which test files to look at. Mention specific "
                           "test files from the repo if you can identify them. Do NOT guess "
                           "exact test commands — point to config files (e.g. tox.ini, "
                           "Makefile, package.json scripts) for how to run tests.",
    "code_hints":          "Key files, functions, or design pointers.",
}

FIELD_DESCRIPTION_OVERRIDES = {
    "bare": {
        "description": "A natural, conversational developer request (1–3 sentences). "
                       "Casual and direct, as if typed in a chat. No markdown, no bullet "
                       "points, no file paths. Just what needs to happen.",
    },
    "concise": {
        "description": "Brief task description (2–4 sentences). State what needs to "
                       "change and why. No implementation details or file paths.",
    },
}


def output_format(hints_level):
    overrides = FIELD_DESCRIPTION_OVERRIDES.get(hints_level, {})
    tags = "\n".join(f"  <{f}>\n    {overrides.get(f, FIELD_DESCRIPTIONS[f])}\n  </{f}>" for f in FIELDS_BY_LEVEL[hints_level])
    return f"Respond with ONLY this XML — nothing outside the tags.\n\n<task>\n{tags}\n</task>"


def build_prompt(row):
    """Returns (prompt, config), or (None, None) if the touched files are too large."""
    config = sample_config(row)
    pr, code = row["pull_request"], row["code"]
    compare_diff = code["compare_diff"] or ""
    base_files = code["base_files_at_base"] or []
    touched_files = code["touched_files"] or []
    repo_files = code["repo_files_at_base"] or []

    if sum(len((f["content"] or "").splitlines()) for f in base_files) > MAX_TOTAL_FILE_LINES:
        return None, None

    # ---- PR context ----
    sections = []
    meta = f"Repository: {code['repo_full_name']}"
    repo_description = (pr["base"]["repo"]["description"] or "").strip()
    if repo_description:
        meta += f" — {repo_description}"
    if config["primary_language"]:
        meta += f"\nPrimary language: {config['primary_language']}"
    meta += f"\nPR title: {pr['title']}\nFiles changed ({len(touched_files)}): {', '.join(touched_files) or '(unknown)'}"
    test_files = [f for f in touched_files if TEST_FILE_RE.search(f)]
    if test_files:
        meta += f"\nTest files in this PR: {', '.join(test_files)}"
    if repo_files:
        shown = sort_repo_files(repo_files)
        more = f" ... [{len(shown) - MAX_REPO_FILES} more files not shown]" if len(shown) > MAX_REPO_FILES else ""
        meta += f"\nRepo files: {', '.join(shown[:MAX_REPO_FILES])}{more}"
    sections.append(("PR METADATA", meta))

    body = (pr["body"] or "").strip()
    if body:
        more = f"\n... [truncated at {MAX_PR_BODY_CHARS} chars]" if len(body) > MAX_PR_BODY_CHARS else ""
        sections.append(("PR DESCRIPTION", body[:MAX_PR_BODY_CHARS] + more))

    subjects = "\n".join(f"  - {c['subject'].strip()}" for c in code["commits"] or [] if (c["subject"] or "").strip())
    if subjects:
        sections.append(("COMMIT SUBJECTS", subjects))

    if compare_diff:
        diff, truncated = truncate_diff(compare_diff)
        sections.append(("COMBINED DIFF" + (" (truncated)" if truncated else ""), diff))

    files = []
    for f in base_files:
        if f["content"]:
            text, truncated = smart_truncate(f["content"], f["path"], compare_diff)
            files.append(f"### {f['path']}{' (diff-relevant regions only)' if truncated else ''}\n```\n{text}\n```")
    if files:
        sections.append(("BASE FILE CONTENTS (state before the change)", "\n\n".join(files)))

    comments = discussion_comments(row["events"] or []) if config["include_comments"] else []
    if comments:
        sections.append(("DISCUSSION COMMENTS", "\n\n".join(f"- {c}" for c in comments)))

    context = "\n\n".join(f"=== {title} ===\n{text}" for title, text in sections)

    # ---- Instructions ----
    rules = (
        "## RULES\n"
        "- Do NOT reproduce the PR title or commit messages verbatim.\n"
        "- Do NOT say \"implement what this PR does\" — describe the goal as an independent task.\n"
        "- The task must be solvable on the repository as-is (before any changes).\n"
        "- Do not reference \"the PR\", \"this diff\", or \"the patch\"."
    )
    if config["hints_level"] in ("standard", "guided", "detailed"):
        rules += (
            "\n- The agent will have the repo already cloned but NO dependencies installed."
            "\n  Environment setup should point to relevant config files (e.g. pyproject.toml,"
            "\n  Makefile, tox.ini) — do NOT fabricate install or test commands."
        )

    prompt = "\n\n".join([
        STYLE_INTROS[config["style"]],
        f"## PERSONA\n{PERSONA_INSTRUCTIONS[config['persona']]}",
        f"## SCOPE\n{SCOPE_INSTRUCTIONS[config['scope_framing']]}",
        f"## WHAT TO INCLUDE (hints level: {config['hints_level']})\n{HINTS_INSTRUCTIONS[config['hints_level']]}",
        rules,
        f"## OUTPUT FORMAT\n{output_format(config['hints_level'])}",
        f"## PR CONTEXT\n{context}",
    ])
    return prompt, config
