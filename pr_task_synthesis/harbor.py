"""
harbor_format.py — Shared Harbor task format constants and generators.

Imported by:
  - agent.py (_export_harbor_task, in-pipeline export)
  - tools/to_harbor.py (fallback post-hoc re-export for old runs)
"""

from typing import Optional
from pathlib import Path
import re


SCHEMA_VERSION = "1.1"

# ---------------------------------------------------------------------------
# Generated file templates
# ---------------------------------------------------------------------------

_SOLVE_SH = """\
#!/bin/bash
set -e
cd /workspace
git apply --whitespace=nowarn /solution/fix.patch
"""

_TEST_SH = """\
#!/bin/bash

# Recreate the /artifacts/evaluation/ layout that eval.sh was synthesized to expect.
# eval.sh was written inside the pipeline assuming these paths; we bridge them here.
mkdir -p /logs/verifier
mkdir -p /artifacts/evaluation

cp /tests/eval.sh /artifacts/evaluation/eval.sh

if [ -f /tests/test.patch ]; then
    cp /tests/test.patch /artifacts/evaluation/test.patch
fi

if [ -d /tests/tests ]; then
    cp -r /tests/tests /artifacts/evaluation/tests
fi

cd /workspace

# Run eval.sh — capture output regardless of exit code.
# eval.sh exits non-zero on test failure by design; || true prevents script abort.
EVAL_OUT=$(bash /artifacts/evaluation/eval.sh 2>&1) || true
echo "$EVAL_OUT"

# Parse OPENENV_EXIT_CODE — non-fatal: || true guards against grep/cut failure.
# If the marker is missing or malformed, EXIT_CODE is empty -> treated as failure.
EXIT_CODE=$(echo "$EVAL_OUT" | grep -o 'OPENENV_EXIT_CODE=[0-9]*' | tail -1 | cut -d= -f2 || true)

# Write reward: 1 only if marker is present and equals 0, else 0.
# Use explicit if/else — never rely on shell one-liner redirection.
if [ "$EXIT_CODE" = "0" ]; then
    echo "1" > /logs/verifier/reward.txt
else
    echo "0" > /logs/verifier/reward.txt
fi
"""

# ---------------------------------------------------------------------------
# Artifact gate constants (used by _export_harbor_task)
# ---------------------------------------------------------------------------

# All three must exist for export to proceed
HARBOR_REQUIRED_ARTIFACTS = [
    "environment/Dockerfile.final",
    "environment/setup_runtime.sh",
    "environment/repo_setup.sh",
    "evaluation/eval.sh",
]

# At least one must exist for export to proceed
HARBOR_VERIFIER_ASSETS = [
    "evaluation/test.patch",
    "evaluation/tests",
]

# ---------------------------------------------------------------------------
# task.toml builder
# ---------------------------------------------------------------------------


def build_task_toml(
    task_input: dict,
    runtime_family: Optional[str],
    pushed_image_ref: Optional[str],
) -> str:
    """
    Assemble and return the full task.toml string for a Harbor task.

    task_input  — the task_input.json dict (fields defined in harbor_inpipeline_export_plan.md)
    runtime_family   — from exploration_report.json; omitted if None
    pushed_image_ref — full ECR URI; docker_image field omitted if None
    """
    task_id       = task_input["task_id"]
    repo_full     = task_input.get("repo_full_name", "")
    git_pr_id     = task_input.get("git_pr_id")
    subtask_index = task_input.get("subtask_index")
    repo          = task_input.get("repo", "")
    base_commit   = task_input.get("base_commit", "")
    domain = task_input.get("domain", "")
    complexity = task_input.get("complexity", "")
    language = task_input.get("primary_language", "")
    star_category = task_input.get("star_category", "")

    # Description
    if repo_full and git_pr_id is not None and subtask_index is not None:
        description = f"OpenEnv: {repo_full} PR #{git_pr_id} subtask {subtask_index}"
    elif repo_full and git_pr_id is not None:
        description = f"OpenEnv: {repo_full} PR #{git_pr_id}"
    else:
        description = f"OpenEnv: {task_id}"

    lines = [
        f'schema_version = "{SCHEMA_VERSION}"',
        "",
        "[task]",
        f'name = "{task_id}"',
        f'description = "{description}"',
        "authors = []",
        "keywords = []",
        "",
        "[metadata]",
        'source = "openenv"',
    ]

    if repo:
        lines.append(f'git_url = "{repo}"')
    if git_pr_id is not None:
        lines.append(f'git_pr_id = "{git_pr_id}"')
    if base_commit:
        lines.append(f'git_base_commit = "{base_commit}"')
    lines.append(f'task_id = "{task_id}"')
    if repo_full:
        lines.append(f'repo_full_name = "{repo_full}"')
    if subtask_index is not None:
        lines.append(f'subtask_index = {subtask_index}')
    if domain:
        lines.append(f'domain = "{domain}"')
    if language:
        lines.append(f'primary_language = "{language}"')
    if runtime_family:
        lines.append(f'runtime_family = "{runtime_family}"')
    if complexity:
        lines.append(f'complexity = "{complexity}"')
    if star_category:
        lines.append(f'star_category = "{star_category}"')
    lines += [
        "",
        "[verifier]",
        "timeout_sec = 600.0",
        "",
        "[agent]",
        "timeout_sec = 900.0",
        "",
        "[environment]",
        "build_timeout_sec = 600.0",
    ]
    if pushed_image_ref:
        lines.append(f'docker_image = "{pushed_image_ref}"')
    lines += [
        'os = "linux"',
        "cpus = 2",
        "memory_mb = 4096",
        "storage_mb = 20480",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# instruction.md builder
# ---------------------------------------------------------------------------


def build_instruction_md(task_input: dict) -> str:
    """
    Return instruction.md content.

    Primary source: task_input['issue'] (original task description from input JSON).
    Fallback: minimal placeholder.
    """
    issue = (task_input.get("issue") or "").strip()
    task_id = task_input.get("task_id", "unknown")

    if issue:
        return issue + "\n"

    return f"# {task_id}\n\nFix the bug described by the associated patch.\n"

# ---------------------------------------------------------------------------
# Patching the ecr push status into task.toml after the fact
# ---------------------------------------------------------------------------
