"""PR -> an agent that builds a runnable, verified environment for it.

Reads tasks from a local JSONL file and runs one Apptainer sandbox per task. Inside, the agent
synthesizes a Dockerfile, a setup script and an eval.sh, then proves the eval script actually
discriminates: it must fail on the repository before the fix and pass after it. The multi-turn
loop lives in agent.py; what the agent is asked to do lives in prompts/.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentdist.agentdist import AgentFlowContext
from agentdist.orchestrator.udf import udf
from agentdist.structures.agent import AgentConfig
from agentdist.structures.dataobject import TaskContext
from agentdist.structures.executor import ContainerExecConfig

from agent import SWEEnvBuilderCustomAgent

MODEL_BASE_URL = os.environ.get("MODEL_BASE_URL", "http://localhost:8000/v1")
MODEL = os.environ.get("MODEL", "Qwen/Qwen3.5-397B-A17B-FP8")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "EMPTY")

SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "sandbox.sif")

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
MAX_TURNS = 16


####
# Agent Configuration
####


@udf()
def load_tasks(path: str, limit: int = 0):
    """Yield one task per line of a JSONL file."""
    yielded = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            task = {
                "task_id": record.get("task_id"),
                "repo_full_name": record.get("repo_full_name"),
                "git_pr_id": record.get("git_pr_id"),
                "git_pr_url": record.get("git_pr_url"),
                "repo": record.get("repo"),
                "base_commit": record.get("base_commit"),
                "head_commit": record.get("head_commit"),
                "base_branch": record.get("base_branch"),
                "fix_patch": record.get("fix_patch"),
                "test_patch": record.get("test_patch"),
                "primary_language": record.get("primary_language"),
                "repo_description": record.get("description"),
                "issue": record.get("issue"),
                "domain": record.get("domain"),
                "star_category": record.get("star_category"),
                "complexity": record.get("complexity"),
            }
            if not all(
                (task["issue"], task["repo"], task["base_commit"], task["fix_patch"])
            ):
                print(
                    f"skipping {task['task_id']}: missing issue/repo/base_commit/fix_patch"
                )
                continue
            yield task
            yielded += 1
            if limit and yielded >= limit:
                return


def make_repo_setup_script(repo: str, base_commit: str) -> str:
    """The clone script staged at /tasks/repo_setup.sh and run as the sandbox comes up."""
    return f"""#!/bin/bash
git clone --revision '{base_commit}' --depth 1 '{repo}' /workspace
chmod 777 /workspace
cd /workspace && git reset --hard '{base_commit}' && git remote remove origin \\
  && git reflog expire --expire=now --all && git gc --prune && git checkout -b master
"""


def task_instruction(task_context: TaskContext) -> str:
    """The first turn. Everything else the agent needs is in its system prompt, which
    prompts/runtime_prompt.md supplies from inside the sandbox."""
    return """
Use the `openenv-manager` agent.

You are running the SWE Builder benchmark environment synthesis workflow for the current task.

Follow the contract in your system prompt exactly.

Task inputs are staged under /tasks/:
- /tasks/fix.patch     (required)
- /tasks/repo_setup.sh (required)
- /tasks/test.patch    (optional)
- /tasks/issue.md      (optional)

Begin the full workflow now.
"""


def task_artifacts(task_context: TaskContext):
    """Write this task's inputs to a temp dir and map them to /tasks/ in the sandbox."""
    data = task_context.data.metadata["data"]
    tmp_dir = tempfile.mkdtemp(prefix="swe_task_")
    artifacts = []

    setup_path = os.path.join(tmp_dir, "repo_setup.sh")
    Path(setup_path).write_text(
        make_repo_setup_script(data["repo"], data["base_commit"])
    )
    artifacts.append((setup_path, "/tasks/repo_setup.sh"))

    fix_path = os.path.join(tmp_dir, "fix.patch")
    Path(fix_path).write_text(data["fix_patch"])
    artifacts.append((fix_path, "/tasks/fix.patch"))

    if data.get("test_patch"):
        test_path = os.path.join(tmp_dir, "test.patch")
        Path(test_path).write_text(data["test_patch"])
        artifacts.append((test_path, "/tasks/test.patch"))

    if data.get("issue"):
        issue_path = os.path.join(tmp_dir, "issue.md")
        Path(issue_path).write_text(data["issue"])
        artifacts.append((issue_path, "/tasks/issue.md"))

    return artifacts


def prompt_artifacts(task_context: TaskContext):
    """Map the agent definitions, skills and the runtime prompt into the sandbox.

    These are what actually decide how the environment gets built, so they travel with the
    task rather than being baked into the image. opencode looks in the home directory, which
    differs between images, so both locations are written.
    """
    for path in sorted((PROMPTS_DIR / "agents").glob("*.md")):
        yield (f"/root/.opencode/agents/{path.name}", str(path))
        yield (f"/home/agent_sandbox/.opencode/agents/{path.name}", str(path))
    for path in sorted((PROMPTS_DIR / "skills").glob("*/SKILL.md")):
        skill = path.parent.name
        yield (f"/root/.opencode/skills/{skill}/SKILL.md", str(path))
        yield (f"/home/agent_sandbox/.opencode/skills/{skill}/SKILL.md", str(path))
    yield ("/tasks/runtime_prompt.md", str(PROMPTS_DIR / "runtime_prompt.md"))


# ---------------------------------------------------------------------------
# The sandbox
# ---------------------------------------------------------------------------


def make_opencode_config(model: str, base_url: str, api_key: str) -> dict:
    """The JSON blob opencode reads from $OPENCODE_CONFIG_CONTENT instead of a config file."""
    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": {
            "*": "allow",
            "edit": "allow",
            "bash": "allow",
            "read": "allow",
            "grep": "allow",
            "glob": "allow",
            "list": "allow",
            "task": "allow",
            "websearch": "allow",
            "webfetch": "allow",
            "external_directory": {
                "/env/*": "allow",
                "/tmp/*": "allow",
                "/opt/*": "allow",
                "/usr/local/*": "allow",
                "/workspace/*": "allow",
                "/workspace_fixed/*": "allow",
                "/artifacts/*": "allow",
                "/tasks/*": "allow",
            },
        },
        "autoupdate": False,
        "provider": {
            "local": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "local",
                "options": {"baseURL": base_url, "apiKey": api_key},
                "models": {model: {"name": model}},
            }
        },
        "model": f"local/{model}",
        "small_model": f"local/{model}",
    }


def agent_config(task_context: TaskContext, image: str, max_turns: int) -> AgentConfig:
    """One Apptainer sandbox per task, holding the repository twice: once before the fix and
    once with it applied, so eval.sh can be checked against both."""
    opencode_config = make_opencode_config(MODEL, MODEL_BASE_URL, MODEL_API_KEY)

    return AgentConfig(
        name="swe-env-builder",
        agent=SWEEnvBuilderCustomAgent,
        backend="apptainer",
        backend_config=ContainerExecConfig(
            name="swe_env_builder_env",
            image=image,
            post_setup_commands=[
                "cat <<EOF > /etc/apt/apt.conf.d/99fake-root-fix\n"
                'APT::Sandbox::User "root";\n'
                'Dir::Log::Terminal "/dev/null";\n'
                "EOF",
                "bash /tasks/repo_setup.sh",
                "cp -r /workspace /workspace_fixed",
                "cd /workspace_fixed && git apply --ignore-space-change --ignore-whitespace "
                "/tasks/fix.patch",
                "mkdir -p /artifacts/status /artifacts/evaluation /artifacts/environment "
                "/artifacts/analysis_logs /artifacts/build_logs /artifacts/verify_logs",
            ],
            env_vars={
                "DEBIAN_FRONTEND": "noninteractive",
                "FAKEROOTDONTTRYCHOWN": 1,
                "OPENCODE_CONFIG_CONTENT": json.dumps(opencode_config),
                "BUILDAH_ISOLATION": "chroot",
                "STORAGE_DRIVER": "vfs",
                "BUILDAH_LAYERS": "false",
                "_BUILDAH_STARTED_IN_USERNS": 1,
                "BUILDAH_OPTS": "--ignore-chown --userns=host",
            },
            secure=True,  # runs the sandbox under `unshare -r`
            env_artifacts=task_artifacts(task_context),
            env_start_timeout=1800,
            skip_remote_env_setup=True,
        ),
        run_dir="/workspace",
        skip_setup=False,
        agent_run_timeout=int(os.environ.get("BUILD_RUN_TIMEOUT", 15120)),
        agent_run_config={
            "max_turns": max_turns,
            "agent_name": "openenv-manager",
            "runtime_prompt_path": "/tasks/runtime_prompt.md",
        },
    )


def save_task_dir(task_dir: str, target_path: str):
    """Copy the finished task directory and the synthesized environment out of the sandbox."""
    name = Path(task_dir).name
    shutil.copytree(task_dir, os.path.join(target_path, name), dirs_exist_ok=True)
    if os.path.isdir("/artifacts"):
        shutil.copytree(
            "/artifacts",
            os.path.join(target_path, name, "artifacts"),
            dirs_exist_ok=True,
        )


####
# Entry Point
####


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tasks", default="data/input.jsonl", help="JSONL file of tasks"
    )
    parser.add_argument(
        "--output-dir", default="runs", help="Directory for per-task artifacts"
    )
    parser.add_argument(
        "--image",
        default=SANDBOX_IMAGE,
        help="Apptainer image: a .sif path or a docker:// URI",
    )
    parser.add_argument(
        "--concurrent", type=int, default=4, help="Tasks built at the same time"
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Stop after N tasks (0 = all)"
    )
    parser.add_argument(
        "--max-turns", type=int, default=MAX_TURNS, help="Outer-loop turns per task"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what each task would run, without starting a sandbox",
    )
    args = parser.parse_args()

    if args.dry_run:
        dry_run(args)
        return

    context = (
        AgentFlowContext.builder.app_name("pr-task-synthesis")
        .config("concurrent_tasks", args.concurrent)
        .config("eager_stage_cleanup", True)
        .config("offload_executor", False)
        .build()
    )

    data_object = context.from_stream(load_tasks)
    data_object.config.instruction = {"path": args.tasks, "limit": args.limit}

    (
        data_object.map(
            instruction=task_instruction,
            func=lambda data: agent_config(data, args.image, args.max_turns),
            artifacts=prompt_artifacts,
        )
        .save(target_path=args.output_dir, save_failed=True, custom_func=save_task_dir)
        .execute()
    )


def dry_run(args):
    """Show what each task would stage and run, without a container runtime.

    This exercises task loading, the clone script and the prompt inventory, which is where
    most configuration mistakes show up.
    """
    tasks = list(load_tasks.func_code["code"](args.tasks, args.limit))
    agents = sorted((PROMPTS_DIR / "agents").glob("*.md"))
    skills = sorted((PROMPTS_DIR / "skills").glob("*/SKILL.md"))

    print(f"{len(tasks)} task(s) from {args.tasks}")
    print(f"image        {args.image}")
    print(f"model        {MODEL} at {MODEL_BASE_URL}")
    print(f"max turns    {args.max_turns}")
    print(f"prompts      {len(agents)} agents, {len(skills)} skills, runtime_prompt.md")
    for path in agents:
        print(f"               /root/.opencode/agents/{path.name}")
    for path in skills:
        print(f"               /root/.opencode/skills/{path.parent.name}/SKILL.md")
    for task in tasks:
        staged = ["/tasks/repo_setup.sh", "/tasks/fix.patch"]
        if task.get("test_patch"):
            staged.append("/tasks/test.patch")
        if task.get("issue"):
            staged.append("/tasks/issue.md")
        print(f"\n--- {task['task_id']}  ({task['repo']} @ {task['base_commit'][:12]})")
        print(f"    staged   {' '.join(staged)}")
        print(f"    apptainer build --sandbox <dir> {args.image}")
        print("    apptainer exec --no-eval --containall --no-home --writable <dir> \\")
        print(
            "        bash -c 'bash /tasks/repo_setup.sh"
            " && cp -r /workspace /workspace_fixed"
            " && cd /workspace_fixed && git apply /tasks/fix.patch'"
        )


if __name__ == "__main__":
    main()
