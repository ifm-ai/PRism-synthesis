# PRism-synthesis

Four synthetic data pipelines built on real GitHub pull requests. Each PR comes with its
metadata and discussion, its commits and patches, the combined diff, the repository file list
and the contents of the touched files before the change. See https://github.com/ifm-ai/PRism-curator for code to download PRs.

**[`pr_thoughts/`](pr_thoughts) — synthesizing developer thoughts.** A merged PR records *what*
changed but not the thinking behind it. We ask an LLM to write only the missing prose — a task
description, the developer's reasoning before each commit (or each file), and a closing summary
— and splice it around the real repository tree, base files and diffs. All code in the
resulting document is real; only the thoughts are synthetic. The result reads like an agentic
coding session grounded in an actual change.

**[`pr_tasks/`](pr_tasks) — synthesizing coding tasks.** A more standard use of the same PRs: an
LLM turns each PR into a standalone task (a direct instruction, a GitHub issue or a spec, with
anything from a one-line request to a detailed plan), which is wrapped into instructions for a
coding agent working in the repository before the change.

**[`pr_task_synthesis/`](pr_task_synthesis) — synthesizing runnable environments.** The first two
pipelines produce text. This one produces something that executes: an agent reads a PR's issue,
explores the repository before the change, and writes a Dockerfile, a setup script and an
`eval.sh` which creates in harbor format where will be used for agentic RL training. The environment is only kept if the eval script fails on the repository before the fix
and passes after it — so the result is a task a model can actually be graded on, not just asked.

**[`pr_chain_agent_datagen/`](pr_chain_agent_datagen) — synthesizing agentic trajectories.** Takes a chain of PRs that
landed one after another in the same repository and asks an agent to implement them in order until token budget reached, in
one working tree, so each turn (which is user turn) starts on what the previous one left behind. Between turns a second
LLM call compacts the work into a handoff. The output is one long multi-turn session grounded in
real successive changes by single repo with the sequence of the pr's.

**Diversity knobs.** `pr_thoughts` and `pr_tasks` draw a few discrete knobs per PR — writing style,
level of detail, persona, amount of hints, how code, diffs and files are shown, how the agent is
instructed, and so on. The knobs change both what the LLM is asked to write and how the
final data is rendered, so a handful of prompt templates can be applied to millions of PRs
while keeping the data diverse.

Each folder has a README describing the pipeline and its files, and a `data/` folder with
examples of every stage. `pr_thoughts` and `pr_tasks` are shown on the same 200 PRs, so the two
outputs can be compared side by side.

The code is meant to be read: it contains the full logic that determines the data, without the batching and cluster plumbing used to run it at scale. It uses vllm, transformers and pyarrow.