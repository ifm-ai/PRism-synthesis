# pr_tasks

Turns a real GitHub PR into a standalone coding task and a full prompt for a coding agent.
An LLM (gpt-oss-120b) reads the PR (metadata, commit subjects, combined diff, files before the
change, discussion) and writes the task that the PR solves, phrased as an independent
assignment that is solvable on the repository before the change.

1. **Generate** (`generate.py`). Skip PRs whose touched files exceed 5000 lines in total, build
   the prompt (skipping prompts over 32k tokens) and ask the LLM for the task as XML.
2. **Agent prompt** (`agent_prompt.py`). Parse the task from the LLM's final answer, render it
   as text and wrap it with general instructions for an agent working in `/workspace`.

## Diversity knobs

- **Task** (`prompt.py`): amount of hints (bare, concise, standard, guided, detailed; larger
  PRs lean towards more hints). The level decides which fields the LLM writes: title,
  description, environment setup, implementation plan, testing hints, code hints. The other
  knobs are style (instruction, GitHub issue, spec), persona (direct or maintainer), scope
  (targeted or open) and whether the PR discussion is shown. The primary language is
  detected from the repository files.
- **Rendering** (`agent_prompt.py`): task text format (markdown, plain, conversational),
  header and separator styles, and section names. The agent instructions vary in verbosity
  (less detailed tasks get more detailed instructions), workflow (phases, checklist,
  free-form), verification (light, standard, strict), honesty guidance, response format and
  language-specific setup hints.

## Files

- `prompt.py`: task knobs and the prompt.
- `generate.py`: runs the LLM over PRs with vLLM, writing `data/generation.jsonl`.
- `agent_prompt.py`: parses the LLM output, renders the task text and builds the agent
  prompt, writing `data/final.jsonl`.
- `data/input.parquet`: the same 200 PRs as in `pr_thoughts`, with only the fields the code
  reads. The ones that fail the size filters of `generate.py` have no generation.
- `data/generation.jsonl`: per PR, the task knobs, the prompt and the raw LLM output
  (`analysis`, the thinking, then `assistantfinal`, the answer).
- `data/final.jsonl`: per PR, the parsed task (`task`), the task as text (`task_text`) and the
  full agent prompt (`agent_prompt`, with the task rendered independently).

Rows are linked across files by `repo_id` and `pr_number`.
