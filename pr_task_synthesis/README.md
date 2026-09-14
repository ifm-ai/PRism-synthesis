# pr_task_synthesis

Turns a real GitHub PR into a *runnable, verified* environment for it. An LLM agent (opencode,
driving a model served over an OpenAI-compatible endpoint) explores the repository at the commit
before the fix and writes a `Dockerfile`, a `setup_runtime.sh` and an `eval.sh` — then has to
prove the eval script is worth anything.

That proof is the point of the pipeline. The sandbox holds the repository twice: `/workspace` as
it was before the change, and `/workspace_fixed` with the PR's real patch applied. A synthesized
`eval.sh` is accepted only if it **fails on the first and passes on the second**. An eval script
that passes on both tests nothing; one that fails on both is broken. The agent never sees the fix
patch — it only ever sees the issue.

1. **Build** (`agent.py`). Up to sixteen outer turns. Each turn runs the manager agent, then
   checks what it produced: are the required artifacts there, do they pass the quality gate, does
   the Dockerfile build under buildah, does the resulting image become a working Apptainer
   container, and does `eval.sh` discriminate. Failures come back as feedback for the next turn.
2. **Judge** (`agent.py`). A solver agent attempts the task in the finished environment and a
   judge scores the resulting trajectory, so a task that is impossible or trivially easy can be
   spotted.
3. **Export** (`harbor.py`, `decision.py`). Write a Harbor task bundle — `task.toml`,
   `instruction.md`, the environment, the tests and the solution — and record a keep-or-drop
   decision for the run.

## Sub-Agents

All sub-agents live in `prompts/agents/`. They are loaded into the container at `/root/.opencode/agents/` and `/home/agent_sandbox/.opencode/agents/`.

| Agent | Role | Owns |
|-------|------|------|
| `openenv-manager` | Inner orchestrator; owns end-to-end workflow | `/artifacts/status/manager.json` |
| `openenv-repository-explorer` | Detects language, build system, test framework, repo structure | `/artifacts/environment/exploration_report.json` |
| `openenv-environment-builder` | Creates runtime (conda/uv/npm/cargo/…), installs project deps, writes activation contract | `/artifacts/environment/environment_request.json`, `setup_runtime.sh` |
| `openenv-eval-builder` | Writes `eval.sh`; copies or synthesizes hidden verifier tests | `/artifacts/evaluation/eval.sh`, `test.patch`, `tests/` |
| `openenv-test-analyst` | Audits `eval.sh`, runs local two-run preflight (testOnly / testWithFix), routes repairs and also checks the oracle verifier and instruction alignment and captures the files required for the `eval.sh` run which is required by the `_export_harbor_task()` method| `/artifacts/analysis_feedback.json`, `analysis_logs/` |
| `openenv-dockerfile-builder` | Builds `Dockerfile.final` and `container_build_plan.json` | `/artifacts/environment/Dockerfile.final` |
| `openenv-build-validator` | Validates container spec with Buildah; exports OCI archive | `/artifacts/environment/openenv_validation.tar`, `/artifacts/build_feedback.json` |
| `openenv-trajectory-judge` | Evaluates a solver trajectory against the quality rubric (see §10) | `/artifacts/trajectory_evaluation.json`, `/artifacts/status/trajectory_judge.json` |
| `openenv-instruction-tuner` | Opt-in. Rewrites `instruction.md` with a behavioral-only clarification when the judge flags an instruction problem  | ` /artifacts/instructions/instruction_v1.md`, ` /artifacts/instructions/instruction_v2.md`, ` /artifacts/instructions/instruction_tuning_log.json`, `/artifacts/status/instruction_tuner.json` |

### Sub-agent invocation hierarchy

```
openenv-manager
  ├── openenv-repository-explorer
  ├── openenv-environment-builder
  │     └── (may call openenv-repository-explorer for clarification)
  ├── openenv-eval-builder
  │     └── (may call openenv-environment-builder for activation commands)
  ├── openenv-test-analyst
  │     ├── (may call openenv-eval-builder to repair eval.sh)
  │     └── (may call openenv-environment-builder to repair runtime setup)
  ├── openenv-dockerfile-builder
  └── openenv-build-validator
        └── (failure routed back to openenv-dockerfile-builder or openenv-environment-builder)
```
`openenv-trajectory-judge` and `openenv-instruction-tuner` are **not** part of this
hierarchy — `openenv-manager` never invokes either. Both run at the outer-loop level,
after the manager's workflow has already succeeded and the container has been built.

### Per-turn sequence

```
for turn in 1..max_turns:
  1. Check time budget remaining
  2. Snapshot existing opencode sessions
  3. Run opencode --agent openenv-manager (runtime_prompt.md as user message)
  4. Collect & save per-turn trajectories (recursive session tree)
  5. _check_required_artifacts()      → all SYNTHESIS_REQUIRED_FILES present?
                                        all status/*.json green (blocks_outer_progress=false)?
                                        reads environment_builder.infrastructure_limited
                                        reads environment_builder.test_runner_reachable
                                        reads test_analyst.hacking_detected
                                        reads manager.blocks_full_outer_turn (block streak)
  6. Manager block streak check       → reads manager.blocks_full_outer_turn:
       - platform_incompatible / infrastructure_limited → immediate early stop
       - hacking_unresolved            → early stop after streak ≥ 2 consecutive blocks
  7. _quality_gate_checks()           → deterministic content quality gate
       a. test_analyst.json           - hacking_detected=true → block
                                      - execution_mode=source_inspection → block
                                      - test_only=0 AND test_with_fix=0 → non-discriminating → block
       b. eval.sh static scan (EVAL_HACK_PATTERNS_RE + EVAL_RC_CAPTURE_RE + EVAL_TEST_RUNNER_RE):
                                      - H1 git state oracle, H3 file-existence oracle
                                      - H4 hardcoded exit before emit_result section
                                      - H5 OPENENV_EXIT_CODE not from $RC, H5b RC=literal
                                      - H5c RC=$? absent, H6 no test-runner invocation
                                      - H7 patch-content inspection, H10 setup_runtime.sh call
       c. Dockerfile.final (DOCKERFILE_VIOLATIONS_RE + DOCKERFILE_REQUIRED_RE):
                                      - eval.sh/workspace/tests baked into image
                                      - repo_setup.sh / setup_runtime.sh COPY+RUN missing
                                      - WORKDIR /workspace missing
  8. _build_image()                   → buildah bud --format docker (+ Apptainer SIF)
  9. _check_workspace_in_image()      → /workspace inside sandbox is non-empty
  10. _verify_eval()
        testOnly:    run eval.sh on buggy /workspace inside Apptainer sandbox → must exit ≠ 0
        testWithFix: git apply fix.patch, run eval.sh → must exit = 0
        + _check_eval_output_quality() on each run:
            >>>>> Start/End markers present, ≥2 non-blank lines, test-runner signal present
  11. _write_verify_feedback()        → /artifacts/verify_feedback.json
  12. If any step fails → compose targeted remediation prompt
        skip_workers: [workers whose status/*.json is already green]
        target_worker: the specific openenv-* agent to re-invoke
      → continue to next turn
  13. On success → _analyze_builder() → solver run + trajectory judge + instruction tuning advice run
  14. _export_harbor_task()           → write Harbor task bundle to /artifacts/harbor_task/
```

###  The outer loop is the interesting part

A single agent turn almost never produces a working environment. What makes this work is that
every check is mechanical and its output is fed back as text:

- **Artifact audit** — are `Dockerfile.final`, `setup_runtime.sh`, `eval.sh` and the rest present
  and non-empty.
- **Quality gate** — a set of anti-shortcut checks. The agent is being asked to write a test that
  fails, and the easiest way to satisfy that is to cheat: hard-code a failure, test nothing, or
  copy the fix into the test. The gate looks for exactly this.
- **Build** — `buildah bud` on the agent's own Dockerfile, inside the sandbox.
- **Container check** — convert to a `.sif` and confirm `/workspace` survived the build.
- **Verify** — run `eval.sh` twice, before and after the fix, and compare.

## Files

- `pipeline.py`: loads tasks, stages `/tasks/`, builds the sandbox config and runs tasks
  concurrently. This is the file you run.
- `agent.py`: the outer loop — turns, audits, quality gate, build, verification, judging, export.
- `harbor.py`: renders `task.toml` and `instruction.md` for the Harbor task bundle.
- `decision.py`: scores a finished run and decides whether to keep it.
- `prompts/runtime_prompt.md`: the contract the manager agent works to, loaded from inside the
  sandbox.
- `prompts/agents/*.md`: the nine sub-agents the manager delegates to — repository explorer,
  environment builder, dockerfile builder, build validator, test analyst, eval builder,
  trajectory judge, instruction tuner.
- `prompts/skills/*/SKILL.md`: three skills — dockerfile buildability review, container build
  validation, and the trajectory rubric.
- `sandbox.def`: the Apptainer image — opencode, buildah, and Apptainer itself, because the
  agent builds container images from inside a container.
- `data/input.jsonl`: five real tasks (issue, repository, base commit, fix patch).
- `data/final.jsonl`: one real successful run — the environment, the verified `eval.sh` and the
  Harbor bundle it produced, after four turns.

Most of what decides the output is in `prompts/`, not in the Python.

## Running it

```bash
apptainer build --fakeroot sandbox.sif sandbox.def

export MODEL_BASE_URL=http://<vllm-host>:8000/v1
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8
export MODEL_API_KEY=...            # whatever your endpoint expects; EMPTY for a bare vLLM

python pipeline.py --tasks data/input.jsonl --output-dir runs --concurrent 4
```

`--dry-run` prints the staged files, the prompt inventory and the sandbox commands for each task
without starting a container.

Nested containers are the one real requirement: buildah and Apptainer both run *inside* the
sandbox, which needs working user namespaces and a subuid/subgid range on the host. The
Kubernetes version of this pipeline got that from a privileged pod with `SYS_ADMIN`; here it comes
from `--fakeroot` and the `unshare -r` that `secure=True` applies.