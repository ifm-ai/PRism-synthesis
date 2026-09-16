---
name: container-build-validation
description: Validate whether a generated container specification is actually buildable by reviewing the Dockerfile, checking the colocated build context, running a real Buildah build, exporting an OCI archive, and classifying failures so they can be routed to the correct fixing agent.
---

# Container Build Validation

Use this skill when a worker needs to determine whether the generated container spec is actually buildable.

This skill is intended for the SWE Builder flow after `Dockerfile.final` has already been written.

## Inputs To Inspect

Read only what you need:
- `/artifacts/environment/Dockerfile.final`
- `/artifacts/environment/container_build_plan.json`
- `/artifacts/environment/environment_request.json`
- `/artifacts/environment/setup_runtime.sh`
- `/artifacts/environment/repo_setup.sh`
- build feedback or prior logs when present

## Core Goal

Answer two questions:
1. Is the container spec buildable?
2. If not, which worker should fix it next?

## Validation Workflow

1. Review the static contract
- `Dockerfile.final` and `container_build_plan.json` should describe the same environment
- `setup_runtime.sh` and `repo_setup.sh` should be assumed colocated with the container specs in the build context
- `eval.sh` and hidden verifier assets must not be baked into the final image unless explicitly required

2. Stage a temporary build context
- create a temp directory
- place or copy in:
  - `Dockerfile.final`
  - `setup_runtime.sh`
  - `repo_setup.sh`
- if `container_build_plan.json` is needed for diagnosis, keep it alongside the temp context

3. Validate Buildah readiness
- check whether `buildah` is available
- prefer a real Buildah build of `Dockerfile.final`
- use Buildah as the authoritative local build executor in this environment
- if Buildah is unavailable, report `tool_unavailable` and stop rather than falling back to Apptainer
- use this standard local validation naming unless your caller explicitly overrides it:
  - local tag: `openenv-validation:latest`
  - archive ref: `openenv-validation:latest`
- preferred commands:
  - `buildah bud --format docker -f Dockerfile.final -t openenv-validation:latest .`
  - `buildah push openenv-validation:latest oci-archive:/artifacts/environment/openenv_validation_oci.tar`

4. Run the build
- run a real Buildah build against the staged context
- use the stable local tag `openenv-validation:latest` for diagnosis unless the caller gives you a specific alternative
- on success, export the built image to `/artifacts/environment/openenv_validation_oci.tar`
- capture full stdout and stderr
- preserve the build log under `/artifacts/build_logs/buildah-build.log`
- prefer keeping the build context as the current working directory and running:
  - `buildah bud --format docker -f Dockerfile.final -t openenv-validation:latest .`
- after a successful build, prefer exporting with:
  - `buildah push openenv-validation:latest oci-archive:/artifacts/environment/openenv_validation_oci.tar`

5. Classify the outcome

**`failure_class`** — fine-grained diagnosis used for routing and attribution:
- `success`
- `dockerfile_render_error`
- `copy_source_missing`
- `base_image_pull_failure`
- `base_image_package_manager_mismatch`
- `system_package_install_failure`
- `runtime_setup_failure`
- `repo_setup_failure`
- `permission_or_filesystem_failure`
- `verifier_asset_packaging_error`
- `tool_unavailable`
- `unknown_build_failure`

**`failure_domain`** — coarse semantic bucket for explainability and auditing (always required):

| Value | Meaning |
|---|---|
| `infra` | Kernel/system constraints the agent cannot influence: UID/GID mapping limits, user namespace policies, kernel security restrictions |
| `spec` | Dockerfile content errors: invalid syntax, wrong base image, missing files in the spec |
| `runtime` | Errors during `RUN` commands at build time: package not found, network failure, command exits non-zero |
| `verifier` | Problems with the eval/verification step rather than the build itself |
| `tooling` | Tool present but behaving incompatibly: storage driver conflicts, graphdriver ambiguity, backend configuration problems, command available but unusable in this execution environment. Not for tool absence (`tool_unavailable` covers that). Not for namespace/permission/kernel-limit issues — those are `infra`. |
| `unknown` | Cannot determine the source |

**`agent_fixable`** — optional binary signal for the outer loop's early-stop control:

Omit this field when uncertain. Uncertainty is the common case — omission is correct and
preferred over guessing. The outer loop falls back to a legacy allowlist when this field
is absent.

- **Omit** when you cannot clearly distinguish artifact problems from platform constraints.
  Examples where you should omit:
  - transient network timeout during `apt-get install`
  - ambiguous non-zero exit with no clear message
  - unknown build failure with no recognizable pattern

- **`false`** only when the failure is clearly caused by environment, platform, or tooling
  constraints that the agent cannot resolve by editing artifacts:
  - user namespace / UID-GID mapping limits → `false`
  - kernel security restrictions blocking `unshare` → `false`
  - storage driver or graphdriver configuration conflict → `false`
  - tool present but completely unusable in this execution environment → `false`

- **`true`** when the failure is clearly in the artifact content the agent controls:
  - Dockerfile syntax or rendering error → `true`
  - wrong package name or command in a `RUN` step → `true`
  - missing `COPY` source caused by the spec → `true`
  - incorrect base image choice → `true`

Worked examples:

```json
// Dockerfile syntax error — agent can fix the spec
{
  "failure_class": "dockerfile_render_error",
  "failure_domain": "spec",
  "agent_fixable": true,
  "route_to": "openenv-dockerfile-builder"
}

// User namespace UID/GID limit — environment constraint, agent cannot fix
{
  "failure_class": "permission_or_filesystem_failure",
  "failure_domain": "infra",
  "agent_fixable": false,
  "route_to": "openenv-dockerfile-builder"
}

// Network timeout during apt-get — transient, unclear if agent can fix
{
  "failure_class": "system_package_install_failure",
  "failure_domain": "runtime",
  "route_to": "openenv-environment-builder"
}
```

6. Route the fix
- `openenv-dockerfile-builder`
  - Dockerfile rendering problems
  - missing `COPY` sources caused by the container spec
  - incorrect mount-point or packaging logic
- `openenv-environment-builder`
  - base image pull failure
  - base image mismatch
  - package manager mismatch
  - system package installation failures
  - `setup_runtime.sh` failures
  - `repo_setup.sh` failures caused by missing environment prep
- `openenv-eval-builder`
  - verifier asset packaging mistakes
  - runtime references that force hidden verifier assets into the image unexpectedly

## Review Bias

- Prefer concrete build blockers over speculative warnings.
- If Buildah is unavailable, report `tool_unavailable` rather than guessing buildability.
- Do not silently "fix" artifacts owned by another worker unless your own prompt explicitly allows it.
- Keep blocker vs warning separation clear.
- When uncertain about `agent_fixable`, omit it — do not guess.

## Output Shape

Produce a compact assessment with:
- `is_finish`
- `build_backend`
- `buildable`
- `failure_class`
- `failure_domain`
- `agent_fixable` (optional — omit when uncertain)
- `route_to`
- `blocking_errors`
- `warnings`
- `next_actions`
- `notes`

If the build succeeded, say so plainly and keep the output short.
