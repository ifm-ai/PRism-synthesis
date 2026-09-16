Use the `openenv-manager` agent.

This prompt is the outer runtime remediation envelope. It is intentionally not
the full workflow definition.

Follow the `openenv-manager` system prompt strictly. Treat the
`openenv-manager` system prompt and its referenced `openenv-*` subagent prompts
as the canonical source of truth for workflow order, artifact ownership,
schemas, and success criteria. If anything in this runtime prompt conflicts
with those prompts, the `openenv-manager` system prompt wins.

The Python orchestrator may append a section named:

```text
Remediation context (from external orchestrator):
...
```

When that section exists, use it as the immediate repair request for this turn.
Do not restart the full workflow from scratch unless the remediation context
explicitly requires a full reset.

## Runtime State

- `/workspace` is the buggy repository checkout.
- `/workspace_fixed` is the fixed reference checkout prepared from `/tasks/fix.patch`.
- `/tasks` contains task inputs such as `fix.patch`, optional `test.patch`, and
  required `repo_setup.sh`.
- `/artifacts` contains all synthesized outputs and status files.
- Existing files under `/artifacts` are the current working state from previous
  turns. Preserve valid artifacts unless their inputs changed or the remediation
  requires rewriting them.

## Hard Prerequisites

- If `/tasks/fix.patch` is missing, stop immediately and write
  `/artifacts/status/manager.json` with a failed status.
- If `/tasks/repo_setup.sh` is missing, stop immediately and write
  `/artifacts/status/manager.json` with a failed status.
- Never synthesize, infer, reconstruct, or approximate `fix.patch`.
- Never rewrite `/tasks/repo_setup.sh`.

## Remediation Behavior

1. Read the appended remediation context first.
2. Identify the affected artifact owner from the manager/subagent ownership contract.
3. Invoke the smallest necessary `openenv-*` worker set first.
4. If a worker changes an upstream artifact, rerun every dependent worker needed
   to restore consistency, even if a skip hint says that worker was previously
   complete.
5. After any verifier or runtime change, rerun `openenv-test-analyst` before
   considering the verifier fixed.
6. After any Dockerfile, runtime setup, repo setup, or packaging change, rerun
   `openenv-build-validator` before considering packaging fixed.
7. Update `/artifacts/status/manager.json` with the final state of the turn.

Skip-worker instructions from the orchestrator are optimization hints only.
They mean the worker's artifacts were valid for the previous state. They do not
prevent rerunning that worker if a dependency changed.

Target-worker instructions from the orchestrator are the preferred first repair
route. The manager may invoke additional dependent workers when required by the
canonical workflow.

## Common Routing

- Missing exploration or repository status artifacts: invoke
  `openenv-repository-explorer`.
- Runtime setup, package installation, activation, toolchain, or test-runner
  reachability failures: invoke `openenv-environment-builder`.
- `eval.sh`, hidden tests, verifier asset paths, hacking signals,
  non-discriminating verifier results, or bad `OPENENV_EXIT_CODE` handling:
  invoke `openenv-eval-builder`, then rerun `openenv-test-analyst`.
- Test analyst failures or suspicious verifier behavior: invoke the worker named
  by `test_analyst` findings, then rerun `openenv-test-analyst`.
- Dockerfile rendering, forbidden `COPY` sources, build-context layout, missing
  `WORKDIR /workspace`, or immutable `repo_setup.sh` drift: invoke
  `openenv-dockerfile-builder`, then rerun `openenv-build-validator`.
- Buildah validation failures: read `/artifacts/build_feedback.json` and route
  according to its `route_to`, `failure_class`, and `failure_domain`.
- External image-level verification failures from `/artifacts/verify_feedback.json`
  or `/artifacts/verify_logs/`: route to `openenv-eval-builder` for verifier
  logic issues, or `openenv-environment-builder` for activation/runtime issues.

## Non-Negotiable Contracts

- Treat `/workspace` and `/workspace_fixed` as immutable reference checkouts
  during synthesis.
- Write task outputs only under `/artifacts`; do not create artifacts under
  `/workspace` or `/workspace_fixed`.
- `/artifacts/environment/repo_setup.sh` must remain an exact copy of
  `/tasks/repo_setup.sh`.
- `Dockerfile.final` must not copy `/workspace`, `eval.sh`, hidden tests, or
  verifier-only patch assets into the image.
- `Dockerfile.final` must use `repo_setup.sh` to materialize `/workspace`, run
  `setup_runtime.sh` after `repo_setup.sh`, and finish with `WORKDIR /workspace`.
- Buildah is the authoritative packaging validation backend.
- Apptainer is runtime-only after packaging succeeds and must not shape
  Dockerfile authoring decisions.
- `eval.sh` must run real tests or real program behavior, not patch/source/file
  inspection as the oracle.
- `eval.sh` must not call or source `setup_runtime.sh`; it must use only the
  activation contract from `/artifacts/environment/environment_request.json`.

## Turn Completion

Finish the turn only when the remediation request is resolved according to the
canonical manager prompt, required dependent workers have been rerun, and
`/artifacts/status/manager.json` accurately reports the outcome.
