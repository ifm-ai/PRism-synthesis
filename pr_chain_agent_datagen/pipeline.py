"""Chain record -> an agent solving N real PRs in one working tree -> a multi-turn trajectory."""

import argparse
import json
import os
import shutil
import sys
from hashlib import md5
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the vendored agentdist

from agentdist.agentdist import AgentFlowContext
from agentdist.orchestrator.udf import udf
from agentdist.structures.agent import AgentConfig
from agentdist.structures.dataobject import TaskContext
from agentdist.structures.executor import ContainerExecConfig

from agent import PRChainCustomAgent

# OpenAI-compatible base URL — vLLM, or anything else that speaks the same wire format.
MODEL_BASE_URL = os.environ.get("MODEL_BASE_URL", "http://localhost:8000/v1")
MODEL = os.environ.get("MODEL", "Qwen/Qwen3.5-397B-A17B-FP8")
MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "EMPTY")

# A .sif path, or a docker:// URI that Apptainer will convert on first use.
SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "sandbox.sif")

MAX_OUTPUT_TOKENS = 121920
CONTEXT_LIMIT = 500000
AGENT_HARNESS_TIMEOUT = 600000
CHAIN_MOUNT = "/chains"          # where the staged chain records appear inside the sandbox

# The repository is cloned into one of these, chosen per task for task diversity
WORKDIR_CANDIDATES = [
    "/workspace", "/testbed", "/repo", "/app", "/project", "/code",
    "/home/user/adam", "/home/john", "/home/bogd", "/home/user/project", "/data/repo",
]


def pick_workdir(task_id: str) -> str:
    """Stable per-task choice, so a rerun of the same chain lands in the same directory."""
    return WORKDIR_CANDIDATES[int(md5(task_id.encode()).hexdigest(), 16) % len(WORKDIR_CANDIDATES)]


####
# Agent Configuration
####


@udf()
def load_chains(path: str, staging_dir: str, limit: int = 0):
    """
    The function to load the chain of pr records, where each chain record is copied to the specified staging path
    """
    Path(staging_dir).mkdir(parents=True, exist_ok=True)
    yielded = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            extra = record.get("extra", {})
            if not extra.get("repo") or not extra.get("base_commit"):
                continue
            task_id = record["task_id"]
            staged = os.path.join(staging_dir, f"{task_id}.json")
            with open(staged, "w") as out:
                json.dump(record, out)
            turns = 1 + len(extra.get("pr_chain", []))
            declared = extra.get("n_prs", turns)
            if declared > turns:
                print(f"{task_id}: declares {declared} PRs but carries content for {turns}; "
                      f"running {turns}")
            yield {
                "task_id": task_id,
                "chain_record_path": f"{CHAIN_MOUNT}/{task_id}.json",
                "n_prs": turns,
                "extra": {"repo": extra["repo"], "base_commit": extra["base_commit"]},
            }
            yielded += 1
            if limit and yielded >= limit:
                return


def chain_instruction(data: TaskContext) -> str:
    """This is dummy instruction where agent ignores"""
    pointer = data.data.metadata["data"]
    return f"solve {pointer['n_prs']}-PR chain for {pointer['extra']['repo']}"






def make_opencode_config(model: str, base_url: str, api_key: str) -> dict:
    """The JSON blob opencode reads from $OPENCODE_CONFIG_CONTENT instead of a config file."""

    _bash_deny = {"*": "allow"}
    for _tool in ("curl", "wget"):
        _bash_deny.update({_tool: "deny", f"{_tool} *": "deny",
                        f"*/{_tool}": "deny", f"*/{_tool} *": "deny"})
    for _sub in ("clone", "fetch", "pull", "ls-remote"):
        for _prefix in ("git", "*/git"):
            _bash_deny.update({f"{_prefix} {_sub}": "deny", f"{_prefix} {_sub} *": "deny",
                            f"{_prefix} * {_sub}": "deny", f"{_prefix} * {_sub} *": "deny"})
    return {
        "$schema": "https://opencode.ai/config.json",
        "permission": {
            "edit": "allow", "read": "allow", "grep": "allow", "glob": "allow",
            "list": "allow", "write": "allow",
            "bash": _bash_deny,
            "websearch": "deny", "webfetch": "deny", "question": "deny",
            "external_directory": {"/**": "allow"},
        },
        "autoupdate": False,
        "provider": {
            "local": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "local",
                "options": {"baseURL": base_url, "timeout": AGENT_HARNESS_TIMEOUT, "apiKey": api_key},
                "models": {
                    model: {
                        "name": model,
                        "reasoning": True,
                        "interleaved": {"field": "reasoning_content"},
                        "limit": {"context": CONTEXT_LIMIT, "output": MAX_OUTPUT_TOKENS},
                        "options": {
                            "chat_template_kwargs": {"enable_thinking": True, "thinking": True},
                            "reasoningEffort": "max",
                            "reasoning": True,
                            "interleaved": {"field": "reasoning_content"},
                        },
                    }
                },
            }
        },
        "agent": {
            "build": {"model": f"local/{model}", "temperature": 1, "top_p": 1},
            "plan": {"model": f"local/{model}", "temperature": 1, "top_p": 1},
        },
        "model": f"local/{model}",
        "small_model": f"local/{model}",
    }


def chain_agent_config(data: TaskContext, image: str, staging_dir: str) -> AgentConfig:
    """One Apptainer sandbox per chain, with the repository cloned at the chain's base commit."""
    pointer = data.data.metadata["data"]
    extra = pointer["extra"]
    n_prs = pointer["n_prs"]
    workdir = pick_workdir(pointer["task_id"])

    opencode_config = make_opencode_config(MODEL, MODEL_BASE_URL, MODEL_API_KEY)

    # Cleaning the git history for hacking proof
    post_setup_commands = [
        "git config --global http.lowSpeedLimit 0",
        "git config --global http.lowSpeedTime 999999",
        "git config --global http.version HTTP/1.1",
        "git config --global http.postBuffer 1048576000",
        f"git clone --revision '{extra['base_commit']}' --depth 1 "
        f"'https://github.com/{extra['repo']}' {workdir}",
        f"chmod 777 {workdir}",
        f"cd {workdir} && git reset --hard '{extra['base_commit']}' && git remote remove origin "
        f"&& git reflog expire --expire=now --all && git gc --prune && git checkout -b master",
    ]

    return AgentConfig(
        name="pr-chain-agent",
        agent=PRChainCustomAgent,
        backend="apptainer",
        backend_config=ContainerExecConfig(
            name="pr_chain_agent_env",
            image=image,
            post_setup_commands=post_setup_commands,
            env_vars={
                "DEBIAN_FRONTEND": "noninteractive",
                "FAKEROOTDONTTRYCHOWN": 1,
                "OPENCODE_CONFIG_CONTENT": json.dumps(opencode_config),
                "OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX": MAX_OUTPUT_TOKENS,
            },
            secure=True,
            storage_mounts={staging_dir: CHAIN_MOUNT},
            env_start_timeout=1200,
            skip_remote_env_setup=True,
        ),
        run_dir=workdir,
        skip_setup=True,
        agent_run_timeout=int(os.environ.get("CHAIN_RUN_TIMEOUT", 1500 * n_prs)),
        agent_run_config={
            "chain_record_path": pointer["chain_record_path"],
            "chain_length": n_prs,
            "synthesis_base_url": MODEL_BASE_URL,
            "synthesis_model": MODEL,
            "synthesis_max_tokens": MAX_OUTPUT_TOKENS,
            "synthesis_extra_args": {
                "reasoning_effort": "high",
                "chat_template_kwargs": {"thinking": True, "enable_thinking": True},
            },
            "synthesis_api_key": MODEL_API_KEY,
            "max_resume_attempts": int(os.environ.get("MAX_RESUME_ATTEMPTS", 3)),
        },
    )


def save_task_dir(task_dir: str, target_path: str):
    """Copy one finished chain's artifacts out of the sandbox's task directory."""
    shutil.copytree(task_dir, os.path.join(target_path, Path(task_dir).name), dirs_exist_ok=True)


####
# Entry Point
####

def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chains", default="data/input.jsonl",
                        help="JSONL file of chain records")
    parser.add_argument("--output-dir", default="runs",
                        help="Directory for per-chain artifacts")
    parser.add_argument("--image", default=SANDBOX_IMAGE,
                        help="Apptainer image: a .sif path or a docker:// URI")
    parser.add_argument("--concurrent", type=int, default=4,
                        help="Chains solved at the same time")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N chains (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what each chain would run, without starting a sandbox")
    args = parser.parse_args()

    staging_dir = os.path.abspath(os.path.join(args.output_dir, "chain_records"))

    if args.dry_run:
        dry_run(args, staging_dir)
        return

    context = (
        AgentFlowContext.builder.app_name("pr-agent-gen")
        .config("concurrent_tasks", args.concurrent)
        .config("eager_stage_cleanup", True)
        .config("skip_env_setup", True)
        .config("offload_executor", False)
        .build()
    )

    data_object = context.from_stream(load_chains)
    data_object.config.instruction = {
        "path": args.chains, "staging_dir": staging_dir, "limit": args.limit,
    }

    (
        data_object.map(
            instruction=chain_instruction,
            func=lambda data: chain_agent_config(data, args.image, staging_dir),
        )
        .save(target_path=args.output_dir, save_failed=True, custom_func=save_task_dir)
        .execute()
    )


def dry_run(args, staging_dir):
    """
    sample dry run
    """
    records = list(load_chains.func_code["code"](args.chains, staging_dir, args.limit))
    print(f"{len(records)} chain(s) from {args.chains}")
    print(f"image        {args.image}")
    print(f"model        {MODEL} at {MODEL_BASE_URL}")
    print(f"bind         {staging_dir} -> {CHAIN_MOUNT}\n")
    for pointer in records:
        workdir = pick_workdir(pointer["task_id"])
        print(f"--- {pointer['task_id']}  ({pointer['n_prs']} PRs, {pointer['extra']['repo']})")
        print(f"    workdir  {workdir}")
        print(f"    record   {pointer['chain_record_path']}")
        print(f"    timeout  {int(os.environ.get('CHAIN_RUN_TIMEOUT', 1500 * pointer['n_prs']))}s")
        print("    apptainer exec --no-eval --containall --no-home --writable \\")
        print(f"        --bind {staging_dir}:{CHAIN_MOUNT} <sandbox> \\")
        print(f"        bash -c 'cd {workdir} && opencode run --thinking --format=json -- ...'")


if __name__ == "__main__":
    main()
