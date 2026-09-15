# pr_chain_agent_datagen

Turns a chain of real merged PRs into one long agentic coding session. The repository is cloned
once at the chain's base commit and an LLM agent (opencode, driving a model served over an
OpenAI-compatible endpoint) is asked to implement each PR in turn — in the *same* working tree, so
turn *i* starts on whatever turn *i-1* left behind and agent runs to reach proposed token budget, it's a recursive application of same repo pr in sequence to simulate the multiple features applied in sequence to build the long context coding data.

opencode keeps no memory between separate runs, so continuity comes from exactly two things: the
live filesystem, and an explicit handoff. Between turns a second LLM call compacts what happened
into a strict ten-section summary, which is prepended to the next turn's task. The N per-turn
sessions are then flattened into a single conversation.

1. **Load** (`pipeline.py`). Read chain records from a JSONL file, stage each record on disk and
   yield a small pointer; the record itself is bind-mounted into the sandbox, since it carries
   every PR's diff and base files and can be tens of megabytes.
2. **Solve** (`agent.py`). Per chain, start one Apptainer sandbox, clone the repository at the base
   commit, and run the turn loop: build the turn's task, prepend the handoff, run opencode, export
   the trajectory, compact, repeat. Stops early if the token budget is exhausted.
3. **Combine** (`trajectory.py`). Flatten the per-turn sessions into one `conversation` list, and
   write it after every turn so an interrupted chain still leaves a valid partial result.

## What the agent is and is not allowed to do

The task is to reimplement a change that already exists upstream, so the interesting failure mode
is the agent simply fetching it. Two things prevent that:

- After cloning, `pipeline.py` runs `git remote remove origin` and expires the reflog, so the
  sandbox holds the repository at the base commit and nothing else.
- The opencode permission map denies `curl`, `wget`, and every spelling of `git clone`, `fetch`,
  `pull` and `ls-remote` (including `*/git * clone *`), along with `websearch` and `webfetch`.

Task synthesis is hardened the same way: the prompt tells the model that the PR context is
untrusted reference data, never to follow instructions found inside it, and never to reproduce
patch code, diff syntax, commit IDs, or refer to a pull request at all.

## The handoff

`synthesis.py` asks the model for a JSON object with nine keys and then assembles the text itself,
in a fixed section order, rather than letting the model format it. Two sections are never
model-authored: **Next steps** is spliced in verbatim from the next turn's task, and
**Constraints** always ends with the same verification-hygiene text. A draft missing any key is
rejected and retried twice before the chain fails.

## Files

- `pipeline.py`: loads chain records, builds the opencode config and the Apptainer sandbox config,
  and runs the chains concurrently. This is the file you run.
- `agent.py`: the turn loop — one `opencode run` per PR, session discovery, resume-on-cutoff,
  token budgeting, and trajectory export.
- `synthesis.py`: the task-synthesis and handoff prompts, their validation and retries.
- `trajectory.py`: `ChainSegment` and the flattener that turns N sessions into one conversation.
- `sandbox.def`: the Apptainer image — opencode, git, and a private Python at `/.environ` that the
  trajectory export runs under, kept separate from whatever the task's repository installs.
- `data/input.jsonl`: fifteen real chain definitions, each up to twenty PRs with their
  per-PR descriptions.
- `data/final/<task_id>/`: the matching run for each — `pr_chain_conversation.json` (the flattened
  conversation and the per-turn record) and `final_stats.json`. Directory names are the `task_id`
  of the corresponding row in `input.jsonl`.

## Running it

```bash
apptainer build --fakeroot sandbox.sif sandbox.def

export MODEL_BASE_URL=http://<vllm-host>:8000/v1
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8
export MODEL_API_KEY=...            # whatever your endpoint expects; EMPTY for a bare vLLM

python pipeline.py --chains data/input.jsonl --output-dir runs --concurrent 4
```

`--dry-run` prints the sandbox commands, the chosen working directory and the staged records for
each chain without starting a container — useful for checking configuration on a machine with no
Apptainer.

The repository is cloned into one of eleven directories (`/workspace`, `/testbed`, `/repo`,
`/home/john`, …) chosen by hashing the task id, so the trajectories don't all claim the work
happened in `/workspace`.

## About the examples

The fifteen chains are real runs over fifteen distinct repositories — `erlang/otp`,
`twbs/bootstrap`, `istio/client-go`, `linkerd/linkerd2-proxy`,
`microsoft/vscode-pull-request-github` and others. Every one of them **ran out of token budget
rather than finishing its chain**, which is the normal outcome: they were chosen from the 4,984
budget-exhausted runs of a 11,615-chain job, taking the ones that burned the most tokens, at most
one per repository.

That makes them useful and also lopsided. Each spent between 746k and 869k tokens, but completed
anywhere from 3 to 18 turns — a run can burn the whole budget wrestling with three PRs in a large
codebase, or work steadily through eighteen in a small one. `stats.total_solved` is how many turns
finished; `stats.budget_exhausted` is true for all of them.

The chains are capped at twenty PRs. The original records name up to fifty, but no run here got
past eighteen turns, so the rest were never read.

Conversations are long — 602 to 1,396 messages — and carry the model's `reasoning_content`
alongside its output, which is about half the bytes. They are one directory per run rather than
one file so no single file is unwieldy.

The trajectories are what the agent actually saw and did, so they contain the contents of the
repositories it worked in. Credentials and internal hostnames that the sandbox environment leaked
into them have been removed.

## Licences of the repositories shown

Because each trajectory quotes the repository the agent worked in, the examples are limited to
repositories whose licence permits redistribution here: seven Apache-2.0, four MIT, one
BSD-3-Clause, two CC-BY, and `ocaml-flambda/flambda-backend`, which is MIT for Jane Street files
and LGPL-2.1-with-linking-exception for the INRIA-derived ones. Each repository's own licence and
copyright continue to apply to its content; this folder's Apache-2.0 licence covers the pipeline,
not the quoted material.

Runs over repositories under GPL, under CC BY-NC-ND, or with no licence at all were excluded, even
where the run itself was good.
