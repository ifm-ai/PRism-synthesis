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

**[`agentdist/`](agentdist) — the runtime the two agentic pipelines run on.** `pr_thoughts` and
`pr_tasks` need nothing but a model: they send a prompt and keep the answer. The other two have to
put an agent in a container, let it edit files and run commands for hours, and collect what it
leaves behind — so they need a runtime, and it ships here rather than being assumed.

A pipeline reads as a small dataflow:

```python
context = AgentFlowContext.builder.app_name("...").config("concurrent_tasks", 4).build()
data    = context.from_stream(load_tasks)            # a @udf generator of records
data.map(instruction=..., func=agent_config, artifacts=...) \
    .save(target_path=..., custom_func=...).execute()
```

`func` returns an `AgentConfig` for each record: which agent class to run, which backend to run it
in, and how to set the sandbox up. The orchestrator starts one sandbox per record, runs the agent
inside it, saves the result and tears the sandbox down, with a semaphore bounding how many run at
once. Swapping `backend="apptainer"` for `"kubernetes"`, `"docker"` or `"local"` changes where the
agent runs and nothing else — the pipeline, the agent and the prompts are identical. Its dependencies are `pydantic`, `cloudpickle`, `colorlog`, `function_schema` and
`opentelemetry`.

The code is meant to be read: it contains the full logic that determines the data. For the two
text pipelines that means no batching or cluster plumbing at all — they use `vllm`, `transformers`
and `pyarrow`. The two agentic pipelines cannot be shown that way, because what they produce
depends on what happens inside a container, so they ship the runtime too.