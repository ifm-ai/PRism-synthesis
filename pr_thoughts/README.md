# pr_thoughts

Turns a real GitHub PR into a document that reads like a developer working through the change:

```
task description
(repository tree)
(files before the change)
for each commit:  developer's reasoning  ->  the commit's real diff
(combined diff and/or files after the change)
summary
```

An LLM (Qwen3.5-397B-A17B) writes only the prose: the task description, the reasoning before
each commit (or before each file of a commit) and the summary. The tree, files and diffs are
spliced in from the PR as they are.

1. **Generate** (`generate.py`). Skip dependency bumps, PRs with broken code data and PRs
   touching 15 or more files. Show the LLM the PR (metadata, discussion, files before the
   change, every commit's diff, combined diff; prompts over 32k tokens are skipped) and ask for
   the prose as XML.
2. **Assemble** (`assemble.py`). Parse the LLM's final answer (never its thinking) and
   interleave it with the real code. Documents over 128k tokens are re-rendered more compactly
   (no post-change files, harder truncation of long base files); those over 512k are dropped.

## Diversity knobs

Drawn per PR, seeded by the PR id.

- **Prompt** (`prompt.py`): style of the task description (GitHub issue, direct instruction,
  conversational, spec), level of detail, with or without a plan, naming the files or not, and
  one reasoning block per commit or per file.
- **Rendering** (`assemble.py`): diff format (unified, search/replace, full file), final section
  (combined diff, files after the change, both), line numbers and their style, file block style
  (`--- path ---` or XML tags), code fences, truncation of long base files, base files up front
  or right before the commit that touches them, repository tree (shown or not; tree, flat or
  indented), where the repository is mentioned, and the connector phrases between sections
  (none 75% of the time).

## Files

- `prompt.py`: PR filter, prompt knobs and the prompt.
- `generate.py`: runs the LLM over PRs with vLLM, writing `data/generation.jsonl`.
- `assemble.py`: parses the LLM output, draws rendering knobs and builds the final documents,
  writing `data/final.jsonl`.
- `connectors.py`: phrases that link sections of a document, and the map from file extension
  to code-fence language.
- `data/input.parquet`: 200 PRs, with only the fields the code reads (the same PRs are used
  in `pr_tasks`).
- `data/generation.jsonl`: per PR, the prompt knobs, the prompt and the raw LLM output
  (thinking, then `</think>`, then the answer).
- `data/final.jsonl`: per PR, the final document (`text`) and its length in tokens.

Rows are linked across files by `repo_id` and `pr_number`.
