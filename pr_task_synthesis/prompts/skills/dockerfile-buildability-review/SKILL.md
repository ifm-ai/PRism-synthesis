---
name: dockerfile-buildability-review
description: Review a generated Dockerfile and its expected build-context files to judge whether the image is likely buildable, identify blocking issues such as missing COPY sources or base-image/package-manager mismatches, and suggest concrete fixes before attempting docker build.
---

# Dockerfile Buildability Review

Use this skill when a worker needs to statically review a generated Dockerfile before attempting a real image build.

This skill is especially useful for `/artifacts/environment/Dockerfile.final` in the SWE Builder workflow.

## Inputs To Inspect

Read only what you need:
- `/artifacts/environment/Dockerfile.final`
- `/artifacts/environment/environment_request.json` when present
- `/artifacts/environment/setup_runtime.sh` when present
- `/artifacts/environment/repo_setup.sh` when present
- any build-context files the Dockerfile references with `COPY` or `ADD`

## Review Goal

Decide whether the Dockerfile is:
- `buildable`
- `probably_buildable`
- `risky`
- `not_buildable`

Focus on likely build success, not style.

## Review Checklist

Check these in order:

1. Dockerfile syntax and stage structure
- obvious malformed instructions
- broken multi-stage references
- invalid `FROM` / `COPY --from` usage

2. Build-context completeness
- every `COPY` or `ADD` source should exist in the intended build context
- flag missing files as blockers
- for this workflow, expect `setup_runtime.sh` and `repo_setup.sh` beside `Dockerfile.final`

3. Base-image and package-manager compatibility
- `apt-get` on Debian/Ubuntu-style bases
- `apk` on Alpine
- `dnf` or `yum` on Fedora/RHEL-like bases
- flag mismatches as blockers or high-risk issues

4. Script path consistency
- copied script destinations should match later `RUN`, `CMD`, or `ENTRYPOINT` usage
- `/opt/benchmark/setup_runtime.sh` and `/opt/benchmark/repo_setup.sh` paths should stay consistent if used

5. Workspace contract
- the Dockerfile must not copy a live `/workspace` into the image
- it should rely on `repo_setup.sh` to materialize `/workspace`
- final `WORKDIR` should be `/workspace`
- flag any workspace snapshotting patterns as blockers, for example:
  - `workspace.tar.gz`
  - `workspace.tgz`
  - `COPY workspace`
  - `ADD workspace`
  - `tar -x` extraction used to materialize `/workspace`
- treat build-context repo archives or copied repo snapshots as contract violations for this workflow


6. Verifier separation
- `eval.sh`, hidden tests, and verifier-only assets should not be baked into the image unless the environment design explicitly requires it

7. Command survivability
- look for `RUN` commands that assume tools were installed earlier but were not
- flag likely missing shell tools, missing directories, or incorrect file permissions

## Output Format

Provide a compact assessment with:
- `buildability_assessment`
- `blocking_risks`
- `warnings`
- `recommended_fixes`

Keep blocker vs warning separation clear.

## Bias

- Prefer concrete, build-affecting issues over speculative ones.
- Do not invent missing files.
- If a source file is absent from the current contract, mark it as a blocker rather than assuming it will appear later.
- If the Dockerfile looks structurally sound and matches the declared build-context contract, say so plainly.
