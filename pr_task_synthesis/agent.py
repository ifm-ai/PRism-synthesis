import base64
import json
import re
import subprocess
import sys
import os
from typing import Optional, Dict, Any
import uuid
import time

import asyncio
from harbor import (
    HARBOR_REQUIRED_ARTIFACTS,
    HARBOR_VERIFIER_ASSETS,
    _SOLVE_SH,
    _TEST_SH,
    build_task_toml,
    build_instruction_md,
)
from decision import (
    compute_trajectory_decision,
    build_instruction_request,
    candidate_instruction_safety,
)

from agentdist.exceptions import AgentSetupError
from agentdist.executors import ExecutionBackend
from agentdist.observability.logging import Logger
from agentdist.structures.agent import (
    AgentContext,
    AgentCoreConfig,
    AgentResult,
    AgentTrajectory,
)
import shlex
from agentdist.agents.opencode import OpenCodeAgent
import tempfile
import cloudpickle
from pathlib import Path
from agentdist.constants import _UDF_WRAPPER, _ENV_ENABLE_CMD
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

logger = Logger.get_logger(__name__)


SUCCESS_STATUSES = {
    "success",
    "completed",
    "complete",
    "done",
    "ok",
    "ready",
    # manager completed synthesis; build infrastructure failed later — non-blocking for outer loop
    "completed_with_build_infrastructure_failure",
    # inner worker completed its synthesis work but recognised the environment is infra-limited;
    # outer _build_image() is the authoritative build check and should still run
    "blocked_by_infrastructure",
    # manager variants that contain FAILURE_TOKENS substrings but represent genuine completion
    "completed_with_infrastructure_limitations",
    "completed_with_infra_constraint",
    "partial_success",
}
FAILURE_TOKENS = ("fail", "error", "blocked", "incomplete")
EVAL_MARKER_RE = re.compile(r"OPENENV_EXIT_CODE=(-?\d+)")

# ── QualityGate: eval.sh hacking patterns ───────────────────────────────────────
# Here we defined 10 hacking patterns
# H1 - git apply/status any git realted check
# H2 - Check if eval.sh is only doing pattern check without actual testing
# H3 - checking if eval.sh is using the fix.patch/test.patch file checks
# H4 - check the exit 0,1 to be tested
# H5 - check OPENENV_EXIT_CODE is $RC
# H5(B) - check $RC is harcoded 0/1
# H5(C) - check $RC=$? or not
# H6 - Check the >>>> START and >>>>End any output
# H7 - check if any test are executed similar to H2
# H8 - (suggested by claude) does eval.sh detect fix application via environment
# H9 - Is testing realted to fix.patch combination of H2,H3
# H10 - check if it directly calls the setup_runtime.sh
EVAL_HACK_PATTERNS_RE = [
    # H1: git state used as oracle
    (
        re.compile(r"\bgit\s+(diff|status\s+--check)\b"),
        "H1:git-state-oracle",
        "  • Remove git diff/status/apply from eval.sh oracle logic.",
    ),
    # H3: file existence as sole oracle
    (
        re.compile(r"\[\s*-[fe]\s+[^]]*(?:fix|patch|added_file)"),
        "H3:file-existence-oracle",
        "  • Only File existance check used as the oracle verifier.",
    ),
    # H4: unconditional exit 0/1 before emit — does NOT flag the required final "exit 0"
    (
        re.compile(r"^\s*exit\s+[01]\s*$", re.MULTILINE),
        "H4:hardcoded-exit-before-emit",
        "  • Remove hardcoded exit 0/exit 1 before emit_result section.",
    ),
    # H5: OPENENV_EXIT_CODE not derived from $RC or ${RC}
    (
        re.compile(r"OPENENV_EXIT_CODE=(?!\$\{?RC\}?\b)\S"),
        "H5:exit-code-not-from-RC",
        "  • OPENENV_EXIT_CODE must be set as: RC=$?; echo OPENENV_EXIT_CODE=$RC",
    ),
    # H5b: RC assigned as literal integer instead of RC=$?
    (
        re.compile(r"\bRC\s*=\s*[01]\b"),
        "H5b:RC-literal-not-from-exit-status",
        "  • eval.sh must invoke a real test runner (pytest/mvn/gradle/etc).",
    ),
    # H7: patch/source file inspection as oracle (grep, rg, awk, sed, python -c)
    (
        re.compile(
            r"\b(grep|rg|awk|sed)\b[^|\n#]*(fix\.patch|test\.patch|/tasks/)"
            r'|python\s+-c\s+[\'"][^\'"]*(fix\.patch|test\.patch|/tasks/)'
        ),
        "H7:patch-content-inspection",
        "  • Remove grep on fix.patch or source files as the oracle.",
    ),
    # H10: sourcing setup_runtime.sh at eval time (it is a build-time artifact)
    (
        re.compile(r"setup_runtime\.sh"),
        "H10:sources-setup-runtime",
        "  • Remove source/bash calls to setup_runtime.sh from eval.sh.",
    ),
]

# Positive check: script MUST contain RC=$? to capture real test-runner exit code.
EVAL_RC_CAPTURE_RE = re.compile(r"\bRC=\$\?")

# Test runner detection — must execute real behavior through a runner or repro harness.
EVAL_TEST_RUNNER_RE = re.compile(
    r"\b("
    r"pytest|python\s+-m\s+pytest|python\s+-m\s+unittest|"
    r"mvn|gradle|gradlew|"
    r"npm\s+(test|run\s+test)|pnpm\s+(test|run\s+test)|yarn\s+(test|run\s+test)|"
    r"jest|vitest|mocha|"
    r"go\s+test|"
    r"cargo\s+test|"
    r"rspec|bundle\s+exec\s+rspec|"
    r"phpunit|"
    r"dotnet\s+test|"
    r"ctest|"
    r"bats|"
    r"bazel\s+test|"
    r"Rscript|"
    r"make\s+(test|check)|tox|nox"
    r")\b"
)

EVAL_COMMENT_RE = re.compile(r"^\s*#.*$", re.MULTILINE)

# ── Quality-Gate: Dockerfile packaging contract violations ────────────────────────
DOCKERFILE_VIOLATIONS_RE = [
    (
        re.compile(r"^(COPY|ADD)\s+\S*eval\.sh", re.MULTILINE | re.IGNORECASE),
        "dockerfile:eval.sh-baked-into-image",
        "  • Remove COPY/ADD of eval.sh from Dockerfile.final.",
    ),
    (
        re.compile(r"^(COPY|ADD)\s+\S*workspace", re.MULTILINE | re.IGNORECASE),
        "dockerfile:workspace-snapshot",
        "  • Remove COPY/ADD of workspace — use repo_setup.sh instead.",
    ),
    (
        re.compile(r"^(COPY|ADD)\s+\S*test\.patch", re.MULTILINE | re.IGNORECASE),
        "dockerfile:test-patch-baked",
        "  • Remove COPY/ADD of test.patch/tests folder from Dockerfile.final.",
    ),
    (
        re.compile(r"^(COPY|ADD)\s+\S*tests/", re.MULTILINE | re.IGNORECASE),
        "dockerfile:tests-dir-baked",
        "  • Remove COPY/ADD of test.patch/tests folder from Dockerfile.final.",
    ),
]
DOCKERFILE_REQUIRED_RE = [
    (
        re.compile(r"(?mi)^\s*COPY\s+repo_setup\.sh\b"),
        "dockerfile:missing-RUN-repo_setup.sh",
        "  • Missing COPY repo_setup.sh in Dockerfile.",
    ),
    (
        re.compile(r"(?mi)^\s*COPY\s+setup_runtime\.sh\b"),
        "dockerfile:missing-COPY-setup_runtime.sh",
        "  • Missing COPY setup_runtime.sh in Dockerfile.",
    ),
    (
        re.compile(r"(?mi)^\s*RUN\s+.*repo_setup\.sh"),
        "dockerfile:missing-RUN-repo_setup.sh",
        "  • Missing RUN repo_setup.sh in Dockerfile.",
    ),
    (
        re.compile(r"(?mi)^\s*RUN\s+.*setup_runtime\.sh"),
        "dockerfile:missing-RUN-setup_runtime.sh",
        "  • Missing RUN setup_runtime.sh in Dockerfile.",
    ),
    (
        re.compile(r"^WORKDIR\s+/workspace\s*$", re.MULTILINE),
        "dockerfile:missing-WORKDIR-workspace",
        "  • Add WORKDIR /workspace as final Dockerfile instruction.",
    ),
]

MANAGER_IMMEDIATE_STOP_REASONS = frozenset(
    {
        "platform_incompatible",
        "infrastructure_limited",
    }
)

INFRASTRUCTURE_FAILURE_TYPES = frozenset(
    {
        "environment_limitation",
        "permission_or_filesystem_failure",
        "tool_unavailable",  # Buildah present but completely unusable in this environment
        "kernel_restriction",  # unshare / user-namespace blocked by kernel policy
    }
)

SYNTHESIS_REQUIRED_FILES = [
    "environment/exploration_report.json",
    "environment/environment_request.json",
    "environment/setup_runtime.sh",
    "environment/repo_setup.sh",
    "evaluation/eval.sh",
    "environment/Dockerfile.final",
    "environment/container_build_plan.json",
    "analysis_feedback.json",
    "analysis_logs/test_only.log",
    "analysis_logs/test_with_fix.log",
    "build_feedback.json",
    "status/repository_explorer.json",
    "status/environment_builder.json",
    "status/eval_builder.json",
    "status/test_analyst.json",
    "status/dockerfile_builder.json",
    "status/build_validator.json",
    "status/manager.json",
]

FULL_SUCCESS_REQUIRED_FILES = SYNTHESIS_REQUIRED_FILES + [
    "environment/openenv_validation_oci.tar"
]
DEFAULT_AGENT_RUN_TIME_BUDGET = 3600

STATUS_WORKERS = [
    "repository_explorer",
    "environment_builder",
    "eval_builder",
    "test_analyst",
    "dockerfile_builder",
    "build_validator",
    "manager",
]

BLOCKING_STATUS_WORKERS = [
    "repository_explorer",
    "environment_builder",
    "eval_builder",
    "test_analyst",
    "dockerfile_builder",
    "manager",
]


class ArtifactAudit(BaseModel):
    ready: bool
    missing: list[str] = Field(default_factory=list)
    blocking_messages: list[str] = Field(default_factory=list)
    status_summary: dict[str, str] = Field(default_factory=dict)
    manager_notes: Optional[str] = None
    manager_full_block: bool = False
    manager_block_reason: str = ""


class BuildResult(BaseModel):
    success: bool
    log: str = ""
    infrastructure_failure: bool = False
    stats: Dict[str, int|float] | None = None


class PreflightCheckResult(BaseModel):
    viable: bool
    detail: Optional[str] = None


class ApptainerBuildResult(BaseModel):
    success: bool
    log: str = ""
    container: Optional[str] = None


class VerifyResult(BaseModel):
    success: bool
    base_exit_code: Optional[int] = None
    fixed_exit_code: Optional[int] = None
    base_output: str = ""
    fixed_output: str = ""
    issues: list[str] = Field(default_factory=list)


class QualityGateResult(BaseModel):
    passed: bool
    eval_signals: list[Any] = Field(default_factory=list)
    dockerfile_signals: list[Any] = Field(default_factory=list)
    analyst_hacking: bool = False
    non_discriminating: bool = False
    source_inspection: bool = False
    source: str = ""  # "test_analyst" | "static_scan" | "both"
    remediation_target: list[str] | None = []
    summary: str = ""


class CheckWorkspaceResult(BaseModel):
    """Result of the /workspace integrity check inside the built container."""

    success: bool
    detail: str = ""


TEST_SIGNAL_RE = re.compile(
    r"(passed|failed|error|ok|FAILED|PASSED|tests\s+run|test\s+session|"
    r"no\s+tests\s+ran|ERRORS|FAILURES|BUILD\s+SUCCESS|BUILD\s+FAILURE|"
    r"assertions|spec\s+\d)",
    re.IGNORECASE,
)


class SWEEnvBuilderCustomAgent(OpenCodeAgent):
    """
    Custom agent-dist Agent that wraps the full multi-turn SWE env-builder orchestration loop
    """

    name = "SWEEnvBuilderCustomAgent"
    version = "v2"

    def __init__(self, exec: ExecutionBackend, agent_config: AgentCoreConfig) -> None:
        super().__init__(exec, agent_config)
        self.max_turns: int = agent_config.agent_run_config.get("max_turns", 1)
        self.agent_name: str = agent_config.agent_run_config.get(
            "agent_name", "openenv-manager"
        )
        self.runtime_prompt_path: str = agent_config.agent_run_config.get(
            "runtime_prompt_path", "/tasks/runtime_prompt.md"
        )
        # Early stop configuration for build environment limitations — stops the agent before turns if preflight check fails, or after turns if a streak of infrastructure-classified build failures is detected.
        self.early_stop_precheck_enabled: bool = agent_config.agent_run_config.get(
            "early_stop_precheck_enabled", True
        )
        self.early_stop_infra_streak_enabled: bool = agent_config.agent_run_config.get(
            "early_stop_infra_streak_enabled", False
        )
        self.early_stop_threshold: int = agent_config.agent_run_config.get(
            "early_stop_threshold", 3
        )

        # Pre-loaded opencode source file

        self.opencode_predownloaded_install_path = agent_config.agent_run_config.get(
            "opencode_predownloaded_install_path", None
        )
        # Set the _analyze_run_budget

        self.analyze_run_time_budget = agent_config.agent_run_config.get(
            "analyze_run_time_budget", 1200
        )
        self.agent_run_time_budget = (
            self._config.run_timeout
            if self._config.run_timeout and self._config.run_timeout > 0
            else DEFAULT_AGENT_RUN_TIME_BUDGET
        )

        self.agent_small_model = agent_config.agent_run_config.get("small_model", None)
        # Set the instruction_tuning_config
        self.instruction_tuning_enabled = agent_config.agent_run_config.get(
            "instruction_tuning_enabled", False
        )
        self.instruction_tuner_run_check = agent_config.agent_run_config.get(
            "instruction_tuner_run_check", False
        )

        # Timing Stats
        self._run_stats = {
            "version": self.__class__.version,
            "total_duration": 0,
            "total_turns": 0,
            "outcome": "",
            "success_turn": None,
            "setup": {},
            "preflight_check": {},
            "turns": [],
            "analyzer_builder": {},
            "harbor_export": {},
            "manager_block_streak": 0,
            "manager_block_last_reason": "",
            "quality_gate_failures": 0,
        }
        if agent_config.agent_run_config.get("extra_attr", None):
            self._run_stats["extra_attr"] = agent_config.agent_run_config["extra_attr"]
        self._extra_attr = agent_config.agent_run_config.get("extra_attr", None)
        self._turn_s = 0
        self._run_turn_s = 0

    @asynccontextmanager
    async def _log_timing_stats(self, operation: dict, key: str):
        """Utitlity method created to log the duration of each operation"""
        _s = time.monotonic()
        try:
            yield
        finally:
            operation[key] = round(time.monotonic() - _s,2)

    def _time_budget_remaining(self):
        """The remaining time budget"""
        cur_s = time.monotonic()
        remaining = self.agent_run_time_budget - int(cur_s - self._run_turn_s)
        return remaining

    def _fresh_run_stats(self):

        self._run_stats = {
            "version": self.__class__.version,
            "total_duration": 0,
            "total_turns": 0,
            "outcome": "",
            "success_turn": None,
            "setup": self._run_stats["setup"],
            "preflight_check": self._run_stats["preflight_check"],
            "turns": [],
            "analyzer_builder": {},
            "harbor_export": {},
            "manager_block_streak": 0,
            "manager_block_last_reason": "",
            "quality_gate_failures": 0,
        }
        if self._extra_attr:
            self._run_stats["extra_attr"] = self._extra_attr
        self._turn_s = 0

    async def setup(self):
        """Ensure the agent's code is present in the container and runtime_prompt.md is in place."""
        async with self._log_timing_stats(self._run_stats["setup"], "root_agent_setup"):
            await super().setup()
        try:
            _ensure_folder = await self._sandbox.exec(
                [
                    "mkdir -p /artifacts/status /artifacts/evaluation /artifacts/environment "
                    "/artifacts/analysis_logs /artifacts/build_logs /artifacts/verify_logs "
                ]
            )
            if _ensure_folder.return_code != 0:
                raise AgentSetupError(
                    f"Agent setup failed due to unable to create the required folder: {_ensure_folder.stderr}"
                )
            # Pre-loop preflight: stop before any LLM turns if quality blockers are present.
            # Only checks tool availability — not uid_map, which only blocks image build.
            if self.early_stop_precheck_enabled:
                async with self._log_timing_stats(
                    self._run_stats["preflight_check"], "preflight_check_environment"
                ):
                    preflight_check = await self._check_build_environment()
                    if not preflight_check.viable:
                        logger.warning(
                            f"[{self.name}] preflight failed: {preflight_check.detail} — stopping before turns"
                        )
                        await self._write_early_stop_status(
                            stop_reason="preflight_failed",
                            stop_stage="preflight",
                            failure_type="environment_limitation",
                            detail=preflight_check.detail,
                            env_failure_streak=0,
                        )
                        # No harbor export — build never attempted, Dockerfile unverified
                        raise AgentSetupError(
                            f"Early stop: build environment not viable ({preflight_check.detail})"
                        )

        except Exception as e:
            logger.error(f"[{self.name}] setup failed: {e}")
            raise AgentSetupError(f"Agent setup failed: {e}")

    @staticmethod
    def _tail(text: str, limit: int = 6000) -> str:
        return text[-limit:] if len(text) > limit else text

    @staticmethod
    def _parse_eval_out_marker(output: str) -> Optional[int]:
        matches = EVAL_MARKER_RE.findall(output)
        return int(matches[-1]) if matches else None

    async def _write_stats(self, task_dir: str) -> None:
        """Finalize task-level duration stats and write <task_dir>/timing.json."""
        if self._turn_s is not None:
            self._run_stats["total_duration"] = round(
                time.monotonic() - self._turn_s, 3
            )

        stats_json = json.dumps(self._run_stats, indent=2, ensure_ascii=False)
        await self._sandbox.exec(
            [f"printf '%s' {shlex.quote(stats_json)} > {task_dir}/stats_timing.json"]
        )
        logger.info(
            f"[{self.name}] stats written: total={self._run_stats['total_duration']}s, "
            f"turns={self._run_stats['total_turns']}, "
            f"outcome={self._run_stats['outcome']}"
        )

    async def run(self, instruction: str, context: AgentContext) -> AgentResult:
        logger.info(
            f"[{self.name}] starting multi-turn loop (max_turns={self.max_turns})"
        )
        # Get the run stats of the fresh run
        self._fresh_run_stats()

        # Ensure required directories exist in the container
        pre_run_commands = await self._sandbox.exec(
            ["mkdir -p " f"{context.task_dir}/prompts " f"{context.task_dir}/logs "]
        )
        if pre_run_commands.return_code != 0:
            return AgentResult(
                status=-1,
                stdout=pre_run_commands.stdout or "",
                stderr=(
                    f"Pre run command Failed due to unable to create the required folder: "
                    f"{pre_run_commands.stderr}"
                    ""
                ),
                trajectory=None,
            )

        pre_copy_commands = await self._sandbox.exec(
            ["cp /tasks/repo_setup.sh /artifacts/environment/repo_setup.sh"]
        )
        if pre_copy_commands.return_code != 0:
            return AgentResult(
                status=-1,
                stdout=pre_copy_commands.stdout or "",
                stderr=(
                    f"repo_setup.sh copy command Failed due to unable to copy: "
                    f"{pre_copy_commands.stderr}"
                    ""
                ),
                trajectory=None,
            )

        base_prompt = await self._load_base_prompt()
        if not base_prompt:
            logger.warning(
                f"[{self.name}] runtime_prompt.md not found at "
                f"{self.runtime_prompt_path}; using instruction as base prompt."
            )
            base_prompt = instruction

        current_prompt = instruction  # first turn uses the task-specific instruction
        last_output = ""
        last_rc = -1
        final_trajectory: Optional[AgentTrajectory] = None
        env_failure_streak = 0  # consecutive infra-classified outer build failures

        self._run_turn_s = time.monotonic()
        for turn in range(1, self.max_turns + 1):
            logger.info(f"[{self.name}] turn {turn}/{self.max_turns}")
            _s = time.monotonic()

            time_budget = self._time_budget_remaining()
            if time_budget <= 0:
                logger.warning(
                    f"""[{self.name}] budget exhausted before turn {turn}: {time_budget:.1f}s """
                )
                self._run_stats["outcome"] = "time_budget_exceeded"
                self._run_stats["time_budget_remaining_at_stop"] = round(time_budget, 1)
                await self._write_stats(context.task_dir)
                return AgentResult(
                    status=-1,
                    stdout=last_output,
                    stderr=(
                        f"Time budget exhausted before turn {turn}: {time_budget:.1f}s "
                        ""
                    ),
                    trajectory=final_trajectory,
                )

            if turn == 1:
                self._turn_s = _s
            self._run_stats["total_turns"] += 1
            _turn_stats = {
                "turn": turn,
                "operations": {},
                "outcome": None,
                "duration": 0,
            }
            # Snapshot the sessions
            async with self._log_timing_stats(
                _turn_stats["operations"], "snapshot_sessions"
            ):
                pre_session_ids = await self._snapshot_sessions(context.run_dir)

            # Run Agent
            async with self._log_timing_stats(
                _turn_stats["operations"], "agent_turn_run"
            ):
                last_output, last_rc = await self._run_agent_turn(
                    current_prompt, turn, context, time_budget
                )
            logger.info(
                f"[{self.name}] turn {turn} exit_code={last_rc}, "
                f"output_len={len(last_output)}"
            )

            # collect the trajectory
            async with self._log_timing_stats(
                _turn_stats["operations"], "collect_turn_trajectories"
            ):
                turn_trajectory = await self._collect_turn_trajectories(
                    turn,
                    context.task_dir,
                    pre_session_ids,
                    context.run_dir,
                    agent_name=self.agent_name,
                )
            if turn_trajectory is not None:
                _prev_trajectory_tokens = 0
                if final_trajectory:
                    _prev_trajectory_tokens = (
                        final_trajectory.full_metrics.output_tokens
                    )
                final_trajectory = turn_trajectory
                final_trajectory.full_metrics.output_tokens += _prev_trajectory_tokens

            # check artifact completeness — streak untouched: build not attempted this turn
            async with self._log_timing_stats(
                _turn_stats["operations"], "audit_artifacts"
            ):
                audit = await self._check_required_artifacts(turn, context)

            # Manager block streak tracking — runs even when audit.ready is False it is similar to the early stop but here we capture the block reason
            # we capture the block reason from the worker and if block is due to platform/infrastructure limited we stop the turn immediately
            # else if we capture like hacking_unresolved we go on to check for early_stop_threashold streak
            if audit.manager_full_block:
                reason = audit.manager_block_reason
                if reason == self._run_stats.get("manager_block_last_reason"):
                    self._run_stats["manager_block_streak"] += 1
                else:
                    self._run_stats["manager_block_streak"] = 1
                    self._run_stats["manager_block_last_reason"] = reason
                streak = self._run_stats["manager_block_streak"]
                reason = self._run_stats["manager_block_last_reason"]
                immediate_stop = reason in MANAGER_IMMEDIATE_STOP_REASONS
                streak_stop = (
                    reason not in MANAGER_IMMEDIATE_STOP_REASONS
                    and streak >= self.early_stop_threshold
                )
                if immediate_stop or streak_stop:
                    logger.warning(
                        f"[{self.name}] manager block streak={streak} reason={reason} "
                        f"immediate={immediate_stop} — early stop"
                    )
                    _turn_stats["outcome"] = f"manager_block_{reason}"
                    _turn_stats["duration"] = round(time.monotonic() - _s, 3)
                    self._run_stats["turns"].append(_turn_stats)
                    await self._write_early_stop_status(
                        stop_reason=f"manager_block{'_immediate' if immediate_stop else '_streak'}:{reason}",
                        stop_stage=f"agent_turn_{turn}",
                        failure_type=(
                            "environment_limitation"
                            if reason in MANAGER_IMMEDIATE_STOP_REASONS
                            else "synthesis_defect"
                        ),
                        detail=reason,
                        env_failure_streak=streak,
                    )
                    await self._write_stats(context.task_dir)
                    return AgentResult(
                        status=-1,
                        stdout=last_output,
                        stderr=f"Manager block ({reason}) after {streak} turn(s)",
                        trajectory=final_trajectory,
                    )
            else:
                self._run_stats["manager_block_streak"] = 0
                self._run_stats["manager_block_last_reason"] = ""

            if not audit.ready:
                logger.info(
                    f"[{self.name}] turn {turn}: artifacts incomplete — "
                    f"missing={audit.missing}, blocking={audit.blocking_messages}"
                )
                _turn_stats["outcome"] = "incomplete_artifacts"
                _turn_stats["duration"] = int(time.monotonic() - _s)
                self._run_stats["turns"].append(_turn_stats)
                self._run_stats["outcome"] = "incomplete_artifacts"
                current_prompt = self._construct_artifact_feedback(
                    base_prompt, audit, last_output
                )
                continue

            # Hard-gate: content quality check before expensive build
            async with self._log_timing_stats(
                _turn_stats["operations"], "quality_gate_checks"
            ):
                gate = await self._quality_gate_checks(turn, context)

            if not gate.passed:
                logger.warning(
                    f"[{self.name}] turn {turn}: quality gate failed — {gate.summary}"
                )
                _turn_stats["outcome"] = "quality_gate_failed"
                _turn_stats["quality_gate_signals"] = (
                    gate.eval_signals + gate.dockerfile_signals
                )
                _turn_stats["duration"] = round(time.monotonic() - _s, 3)
                self._run_stats["turns"].append(_turn_stats)
                self._run_stats["outcome"] = "quality_gate_failed"
                self._run_stats["quality_gate_failures"] = (
                    self._run_stats.get("quality_gate_failures", 0) + 1
                )
                current_prompt = self._construct_quality_gate_feedback(
                    base_prompt, gate, last_output
                )
                continue

            # Check Apptainer build
            async with self._log_timing_stats(
                _turn_stats["operations"], "audit_image_build"
            ):
                build = await self._build_image(turn, context)
            _turn_stats["operations"]["image_build_breakdown"] = build.stats
            if not build.success:
                _turn_stats["outcome"] = "build_failed"
                _turn_stats["duration"] = int(time.monotonic() - _s)

                self._run_stats["turns"].append(_turn_stats)
                self._run_stats["outcome"] = "build_failed"
                if (
                    self.early_stop_infra_streak_enabled
                    and build.infrastructure_failure
                ):
                    env_failure_streak += 1
                    logger.warning(
                        f"[{self.name}] turn {turn}: infra failure streak "
                        f"{env_failure_streak}/{self.early_stop_threshold}"
                    )
                    if env_failure_streak >= self.early_stop_threshold:
                        await self._write_early_stop_status(
                            stop_reason="consecutive_infrastructure_failures",
                            stop_stage=f"build_turn_{turn}",
                            failure_type="environment_limitation",
                            detail=None,
                            env_failure_streak=env_failure_streak,
                        )
                        # No harbor export — build failed, Dockerfile unverified
                        await self._write_stats(context.task_dir)
                        return AgentResult(
                            status=-1,
                            stdout=last_output,
                            stderr=(
                                f"Early stop: {env_failure_streak} consecutive "
                                f"infrastructure build failures"
                            ),
                            trajectory=final_trajectory,
                        )
                else:
                    env_failure_streak = (
                        0  # reset: non-infra failure or streak disabled
                    )
                logger.info(f"[{self.name}] turn {turn}: Apptainer build failed.")
                current_prompt = self._construct_build_feedback(base_prompt, build.log)
                continue

            env_failure_streak = 0  # build succeeded — reset streak

            # Check eval.sh verification
            async with self._log_timing_stats(
                _turn_stats["operations"], "eval_verification"
            ):
                verify = await self._verify_eval(turn, context)
            await self._write_verify_feedback(verify)
            if not verify.success:
                _turn_stats["outcome"] = "eval_verification_failed"
                _turn_stats["duration"] = int(time.monotonic() - _s)
                self._run_stats["turns"].append(_turn_stats)
                self._run_stats["outcome"] = "eval_verification_failed"
                logger.info(
                    f"[{self.name}] turn {turn}: verification failed — "
                    f"{verify.issues}"
                )
                current_prompt = self._construct_verify_feedback(base_prompt, verify)
                continue

            # Just Logging all checks passed
            logger.info(f"[{self.name}] turn {turn}: SUCCESS")
            _turn_stats["outcome"] = "success"
            _turn_stats["duration"] = int(time.monotonic() - _s)
            self._run_stats["turns"].append(_turn_stats)
            self._run_stats["outcome"] = "success"
            self._run_stats["success_turn"] = turn
            async with self._log_timing_stats(
                self._run_stats["analyzer_builder"], "analyzer_builder"
            ):
                await self._analyze_builder(context.task_dir, context.run_dir)
            async with self._log_timing_stats(
                self._run_stats["harbor_export"], "export_harbor_task"
            ):
                await self._export_harbor_task(context)
            await self._write_stats(context.task_dir)
            return AgentResult(
                status=0,
                stdout=last_output,
                stderr=None,
                trajectory=final_trajectory,
            )

        logger.error(f"[{self.name}] failed after {self.max_turns} turns.")
        # No harbor export — task did not reach full success (build + verify)
        self._run_stats["outcome"] = "failed"
        await self._write_stats(context.task_dir)
        return AgentResult(
            status=-1,
            stdout=last_output,
            stderr=f"SWEEnvBuilderCustomAgent failed after {self.max_turns} turns.",
            trajectory=final_trajectory,
        )

    async def _load_base_prompt(self) -> str:
        result = await self._sandbox.exec(["cat", self.runtime_prompt_path])
        return result.stdout.strip() if result.return_code == 0 else ""

    async def _run_agent_turn(
        self,
        prompt: str,
        attempt: int,
        context: AgentContext,
        timeout_budget: int = DEFAULT_AGENT_RUN_TIME_BUDGET,
    ) -> tuple[str, int]:
        """Write the prompt to a file, then invoke opencode run --agent."""
        prompt_path = f"{context.task_dir}/prompts/prompt-{attempt:02d}.md"
        out_path = f"{context.task_dir}/logs/opencode-turn-{attempt:02d}.out"
        out_log = f"{context.task_dir}/logs/opencode-turn-{attempt:02d}.log"

        # Write prompt file — printf is safer than echo for multi-line/arbitrary content
        write_cmd = [
            f"printf '%s' {shlex.quote(prompt)} > {shlex.quote(prompt_path)}",
        ]
        result = await self._sandbox.exec(write_cmd)
        if result.return_code != 0:
            logger.warning(
                f"[{self.name}] could not write prompt file: {result.stderr}"
            )

        # Run opencode via bash so shell features (redirection, process substitution,
        # command substitution) are interpreted correctly.
        run_cmd = [
            f"opencode --agent {shlex.quote(self.agent_name)} run --format=json -- "
            f'"$(cat {shlex.quote(prompt_path)})" '
            f"> >(tee {shlex.quote(out_path)}) "
            f"2> >(tee {shlex.quote(out_log)}) < /dev/null",
        ]
        result = await self._sandbox.exec(
            run_cmd,
            timeout=timeout_budget,
            cwd=context.run_dir,
        )
        out_result = await self._sandbox.exec(["cat", out_path])
        output = (
            out_result.stdout if out_result.return_code == 0 else result.stdout or ""
        )
        return output, result.return_code

    async def _check_required_artifacts(
        self, attempt: int, context: AgentContext
    ) -> ArtifactAudit:
        """Read status files and required artifact paths from inside the container."""
        missing = []
        for rel_path in SYNTHESIS_REQUIRED_FILES:
            full_path = f"/artifacts/{rel_path}"
            result = await self._sandbox.exec(
                ["test", "-f", full_path, "&&", "echo ok", "||", "echo missing"]
            )
            if result.stdout.strip() != "ok":
                missing.append(rel_path)

        # Check verifier asset for better logging
        patch_result = await self._sandbox.exec(
            [
                "test",
                "-f",
                "/artifacts/evaluation/test.patch",
                "&&",
                "echo ok",
                "||",
                "echo missing",
            ]
        )
        tests_result = await self._sandbox.exec(
            [
                "find /artifacts/evaluation/tests",
                "-type f",
                "2>/dev/null",
                "|",
                "head -1",
                "|",
                "grep -q .",
                "&&",
                "echo ok",
                "||",
                "echo missing",
            ]
        )
        if patch_result.stdout.strip() != "ok" and tests_result.stdout.strip() != "ok":
            missing.append("evaluation/test.patch or evaluation/tests/*")

        # Parse status files
        status_summary = {}
        blocking_messages = []
        manager_notes = None
        # Extract manager-level turn-exhaustion signal (blocks_full_outer_turn)
        manager_full_block = False
        manager_block_reason = ""

        for worker in STATUS_WORKERS:
            status_path = f"/artifacts/status/{worker}.json"
            result = await self._sandbox.exec(["cat", status_path, "2>/dev/null"])
            if result.return_code != 0 or not result.stdout.strip():
                continue
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                status_summary[worker] = "invalid-json"
                blocking_messages.append(f"{worker}.status=invalid-json")
                continue

            status_val = payload.get("status")
            notes_val = payload.get("notes")
            if isinstance(notes_val, list):
                notes_val = "; ".join(str(x) for x in notes_val)
            if status_val is not None:
                s = str(status_val)
                status_summary[worker] = s
                if worker in BLOCKING_STATUS_WORKERS:
                    blocks = payload.get("blocks_outer_progress")
                    if blocks is not None:
                        # Explicit structured field — use it directly, ignore status text.
                        if blocks is True:
                            blocking_messages.append(
                                f"{worker}.status={s} (blocks_outer_progress=true)"
                            )
                    else:
                        # Legacy fallback: infer from free-form status text.
                        lowered = s.lower()
                        if lowered not in SUCCESS_STATUSES and any(
                            tok in lowered for tok in FAILURE_TOKENS
                        ):
                            blocking_messages.append(f"{worker}.status={s}")
            if worker == "test_analyst":
                if payload.get("hacking_detected", False):
                    signals = payload.get("hacking_signals", [])
                    blocking_messages.append(
                        f"{worker}.hacking_detected=true signals={signals}"
                    )

            if worker == "environment_builder":
                # infrastructure_limited: record for context but do NOT block here —
                # _build_image is the authoritative check; manager handles the stop.
                if payload.get("infrastructure_limited") is True:
                    reason = payload.get("infrastructure_reason", "unspecified")
                    status_summary["infrastructure_limited"] = str(reason)
                # test_runner_reachable=false is a synthesis defect — block outer progress
                if payload.get("test_runner_reachable") is False:
                    blocking_messages.append(
                        "environment_builder.test_runner_reachable=false — "
                        "no test runner confirmed during synthesis"
                    )

            if worker == "manager" and notes_val:
                manager_notes = str(notes_val)

            if worker == "manager":
                _manager_full_block = bool(payload.get("blocks_full_outer_turn"))
                _manager_block_reason = payload.get("blocks_reason", "")
                if _manager_block_reason in [
                    "platform_incompatible",
                    "infrastructure_limited",
                    "hacking_unresolved",
                ]:
                    manager_full_block = _manager_full_block
                    manager_block_reason = _manager_block_reason

        return ArtifactAudit(
            ready=not missing and not blocking_messages,
            missing=missing,
            blocking_messages=blocking_messages,
            status_summary=status_summary,
            manager_notes=manager_notes,
            manager_full_block=manager_full_block,
            manager_block_reason=manager_block_reason,
        )

    async def _quality_gate_checks(
        self, turn: int, context: AgentContext
    ) -> "QualityGateResult":
        """
        Deterministic Quality gate that runs after artifact presence is confirmed where the created important artifacts like eval.sh, dockerfile
        are in defined templates

        Checkss:
          1. test_analyst.json  — hacking_detected, non_discriminating, source_inspection
          2. eval.sh static scan — regex patterns for hacking shortcuts
          3. Dockerfile.final   — packaging contract violations

        Returns QualityGateResult with passed=True when all checks clear.
        """
        # Read test analyst to check the singals like hacking, deterministic signals
        analyst_raw = await self._sandbox.exec(
            ["cat /artifacts/status/test_analyst.json 2>/dev/null"]
        )
        analyst_feedback_raw = await self._sandbox.exec(
            ["cat /artifacts/analysis_feedback.json 2>/dev/null"]
        )
        analyst = {}
        if analyst_raw.return_code == 0 and analyst_raw.stdout.strip():
            try:
                analyst = json.loads(analyst_raw.stdout)
            except json.JSONDecodeError:
                pass

        analyst_feedback = {}
        if (
            analyst_feedback_raw.return_code == 0
            and analyst_feedback_raw.stdout.strip()
        ):
            try:
                analyst_feedback = json.loads(analyst_feedback_raw.stdout)
            except json.JSONDecodeError:
                pass

        analyst_hacking = bool(analyst.get("hacking_detected"))
        hacking_signals = analyst_feedback.get("hacking_signals") or []
        ov = analyst.get("official_verifier") or {}
        exec_mode = ov.get("execution_mode", "")
        source_inspection = exec_mode in ("source_inspection", "could_not_execute")
        non_discriminating = bool(analyst.get("non_discriminating"))
        test_only_code = ov.get("test_only_exit_code")
        test_with_fix_code = ov.get("test_with_fix_exit_code")

        # Set the discriminating path where the
        if (
            exec_mode == "real_execution"
            and test_only_code == 0
            and test_with_fix_code == 0
        ):
            non_discriminating = True

        if analyst_hacking:
            logger.warning(
                f"[{self.name}] quality_gate turn {turn}: "
                f"hacking_detected=true from test_analyst signals={hacking_signals}"
            )
            return QualityGateResult(
                passed=False,
                eval_signals=hacking_signals,
                analyst_hacking=True,
                source="test_analyst",
                remediation_target=["openenv-eval-builder"],
                summary=f"Verifier hacking detected by test-analyst: {hacking_signals}",
            )

        if source_inspection:
            logger.warning(
                f"[{self.name}] quality_gate turn {turn}: "
                f"test_analyst execution_mode={exec_mode} — source inspection, not real execution"
            )
            notes_lower = (analyst.get("notes") or "").lower()
            if (
                "test_runner" in notes_lower
                or "runner" in notes_lower
                or "unavailable" in notes_lower
            ):
                si_target = "openenv-environment-builder"
            else:
                si_target = "openenv-manager"
            return QualityGateResult(
                passed=False,
                source_inspection=True,
                source="test_analyst",
                remediation_target=[si_target],
                summary=f"Verifier used source inspection ({exec_mode}) — route to {si_target}",
            )

        if non_discriminating:
            logger.warning(
                f"[{self.name}] quality_gate turn {turn}: non_discriminating verifier "
                f"(test_only={test_only_code}, test_with_fix={test_with_fix_code})"
            )
            return QualityGateResult(
                passed=False,
                non_discriminating=True,
                source="test_analyst",
                remediation_target=["openenv-eval-builder"],
                summary="Verifier is non-discriminating: passes on both buggy and fixed workspace",
            )

        # eval.sh static code analysis
        eval_raw = await self._sandbox.exec(
            ["cat /artifacts/evaluation/eval.sh 2>/dev/null"]
        )
        eval_signals = []

        if eval_raw.return_code == 0 and eval_raw.stdout:
            content = eval_raw.stdout

            # Partition on section marker BEFORE stripping comments —
            # stripping first would remove "# openenv: emit_result" itself.
            pre_emit_raw, _, _ = content.partition("# openenv: emit_result")

            clean = EVAL_COMMENT_RE.sub("", content)
            pre_emit = EVAL_COMMENT_RE.sub("", pre_emit_raw)

            for pattern, label, issue_desc in EVAL_HACK_PATTERNS_RE:
                # H4 only applies before emit_result to avoid flagging the required final exit 0
                target = pre_emit if "H4" in label else clean
                if pattern.search(target):
                    eval_signals.append((label, issue_desc))

            # H5c: positive check — RC=$? must be present
            if not EVAL_RC_CAPTURE_RE.search(clean):
                eval_signals.append(
                    (
                        "H5c:RC-never-set-from-exit-status",
                        "  • OPENENV_EXIT_CODE must be set as: RC=$?; echo OPENENV_EXIT_CODE=$RC",
                    )
                )

            # H6: must invoke a real test runner or repro harness
            if not EVAL_TEST_RUNNER_RE.search(clean):
                eval_signals.append(
                    (
                        "H6:no-test-runner-invocation",
                        " • No test runner invocation identified",
                    )
                )

        # Dockerfile.final contract violations
        df_raw = await self._sandbox.exec(
            ["cat /artifacts/environment/Dockerfile.final 2>/dev/null"]
        )
        dockerfile_signals = []

        if df_raw.return_code == 0 and df_raw.stdout:
            df_content = df_raw.stdout
            for pattern, label, issue_desc in DOCKERFILE_VIOLATIONS_RE:
                if pattern.search(df_content):
                    dockerfile_signals.append((label, issue_desc))
            for pattern, label, issue_desc in DOCKERFILE_REQUIRED_RE:
                if not pattern.search(df_content):
                    dockerfile_signals.append((label, issue_desc))
            repo_run = re.search(r"(?mi)^\s*RUN\s+.*repo_setup\.sh", df_content)
            setup_run = re.search(r"(?mi)^\s*RUN\s+.*setup_runtime\.sh", df_content)
            if repo_run and setup_run and repo_run.start() > setup_run.start():
                dockerfile_signals.append(
                    (
                        "dockerfile:RUN-setup_runtime.sh-before-repo_setup.sh",
                        " • Dockerfile must run repo_setup.sh before setup_runtime.sh.",
                    )
                )
        compare = await self._sandbox.exec(
            ["cmp -s /tasks/repo_setup.sh /artifacts/environment/repo_setup.sh"]
        )
        if compare.return_code != 0:
            dockerfile_signals.append(
                (
                    "MODIFIED-repo_setup.sh",
                    " • repo_setup.sh differs from immutable /tasks/repo_setup.sh",
                )
            )
            pre_copy_commands = await self._sandbox.exec(
                ["cp /tasks/repo_setup.sh /artifacts/environment/repo_setup.sh"]
            )

        # Verifier alignment gate
        if analyst_feedback:
            try:
                veria = analyst_feedback.get("verifier_alignment") or {}
                if veria.get("blocks_outer_progress") is True:
                    va_status = veria.get("status", "verifier_misaligned")
                    va_overlap = veria.get("target_overlap", "unknown")
                    rfa = veria.get("required_files_audit") or {}
                    path_traversal_violations = rfa.get("path_traversal_violations", [])
                    flagged = rfa.get("flagged_unnecessary", {})
                    detail = (
                        f"• target verifier overlap with the patch is {va_overlap}"
                        + (
                            f", flagged uncessary files not useful in required verifier files which are {list(flagged.keys())}"
                            if flagged
                            else ""
                        )
                        + (
                            f", path violation in provided required verifier files list are {list(path_traversal_violations)}"
                            if path_traversal_violations
                            else ""
                        )
                    )
                    logger.warning(
                        f"[{self.name}] quality_gate turn {turn}: "
                        f"verifier alignment blocked — {detail}"
                    )
                    return QualityGateResult(
                        passed=False,
                        eval_signals=[
                            (
                                "V1:verifier-alignment-misaligned",
                                f"{detail} — route to openenv-eval-builder",
                            )
                        ],
                        source="test_analyst",
                        remediation_target=["openenv-eval-builder"],
                        summary=f"Verifier alignment gate: {va_status}",
                    )

            except (json.JSONDecodeError, TypeError):
                pass
        all_signals = eval_signals + dockerfile_signals
        if not all_signals:
            return QualityGateResult(passed=True)

        if eval_signals and dockerfile_signals:
            target = ["openenv-eval-builder", "openenv-dockerfile-builder"]
            source = "both"
        elif eval_signals:
            target = ["openenv-eval-builder"]
            source = "static_scan"
        else:
            target = ["openenv-dockerfile-builder"]
            source = "static_scan"

        logger.warning(
            f"[{self.name}] quality_gate turn {turn}: "
            f"static scan fired — eval={eval_signals} dockerfile={dockerfile_signals}"
        )
        return QualityGateResult(
            passed=False,
            eval_signals=eval_signals,
            dockerfile_signals=dockerfile_signals,
            source=source,
            remediation_target=target,
            summary=f"Static scan: {all_signals}",
        )

    def _construct_quality_gate_feedback(
        self, base_prompt: str, gate: "QualityGateResult", agent_output: str
    ) -> str:
        lines = ["Quality gate check failed before container build."]

        if gate.analyst_hacking:
            lines.append(
                f"test-analyst reported hacking_detected=true. "
                f"Signals: {gate.eval_signals}. "
                "Re-invoke openenv-eval-builder with these exact signals and require "
                "a real test runner invocation with OPENENV_EXIT_CODE derived from RC=$?."
            )
        elif gate.source_inspection:
            lines.append(
                "test-analyst reported execution_mode=source_inspection — "
                "the verifier did not run real tests. "
                "Re-invoke openenv-environment-builder to validate the test runner is "
                "reachable (test_runner_reachable=true), then re-invoke openenv-eval-builder."
            )
        elif gate.non_discriminating:
            lines.append(
                "Verifier is non-discriminating: OPENENV_EXIT_CODE=0 on both buggy and "
                "fixed workspace. Re-invoke openenv-eval-builder to target tests that "
                "specifically exercise the behaviour changed by fix.patch."
            )

        if gate.eval_signals:
            _eval_singals_cmd = [_c[0] for _c in gate.eval_signals]
            _eval_singals_iss = [_c[1] for _c in gate.eval_signals]
            lines.append(f"eval.sh static scan fired: {_eval_singals_cmd}.")
            lines.extend(_eval_singals_iss)

        if gate.dockerfile_signals:
            _dockerfile_singals_cmd = [_c[0] for _c in gate.dockerfile_signals]
            _dockerfile_singals_iss = [_c[1] for _c in gate.dockerfile_signals]
            lines.append(f"Dockerfile violations: {_dockerfile_singals_cmd}.")
            lines.extend(_dockerfile_singals_iss)

        heading = "\n".join(lines)
        skip_workers: list[str] = []
        if not gate.dockerfile_signals:
            skip_workers.append("openenv-dockerfile-builder")
        if (
            not gate.eval_signals
            and not gate.analyst_hacking
            and not gate.source_inspection
        ):
            skip_workers.append("openenv-eval-builder")
            skip_workers.append("openenv-test-analyst")
        target = (
            ",".join(gate.remediation_target)
            if len(gate.remediation_target) > 0
            else ""
        )
        return self._construct_prompt(
            base_prompt,
            heading,
            skip_workers,
            target,
            self.__class__._tail(agent_output),
        )

    async def _build_image(self, attempt: int, context: AgentContext) -> BuildResult:
        """Stage build context and run buildah bud inside the container."""
        _build_timestats = {}
        log_path = f"/artifacts/build_logs/outer-build-attempt-{attempt:02d}.log"
        stage_cmd = (
            "set -euo pipefail;"
            "mkdir -p /tmp/swe_env_build_ctx;"
            "rm -rf /tmp/swe_env_build_ctx;"
            f"cp /artifacts/environment/Dockerfile.final  /tmp/swe_env_build_ctx/;"
            f"cp /artifacts/environment/setup_runtime.sh  /tmp/swe_env_build_ctx/;"
            f"cp /artifacts/environment/repo_setup.sh     /tmp/swe_env_build_ctx/;"
            f"chmod +x /tmp/swe_env_build_ctx/*.sh;"
            "rm -rf /tmp/swe_built_sandbox;"
            "cd /tmp/swe_env_build_ctx;"
            f"buildah bud --format docker -f Dockerfile.final -t openenv-validation:latest . 2>&1 | tee {log_path}"
        )
        async with self._log_timing_stats(_build_timestats, "buildah_bud"):
            result = await self._sandbox.exec(
                [stage_cmd],
                timeout=1800,
            )
        log_text = result.stdout or ""
        if result.stderr:
            log_text += "\n" + result.stderr
        if result.return_code == 0:
            async with self._log_timing_stats(_build_timestats, "apptainer_build"):
                apptainer_result = await self._build_apptainer_image(attempt, context)
            if not apptainer_result.success:
                return BuildResult(
                    success=False, log=apptainer_result.log, stats=_build_timestats
                )
            try:
                if apptainer_result.success:
                    build_image = await self._build_apptainer_container()
                    if build_image.success:
                        async with self._log_timing_stats(
                            _build_timestats, "workspace_check"
                        ):
                            ws_result = await self._check_workspace_in_image(
                                build_image.container
                            )
                        if not ws_result.success:
                            logger.warning(
                                f"[build_image]::worskpace_check=failed attempt {attempt}: workspace check FAILED — {ws_result.detail}"
                            )
                            return BuildResult(
                                success=False,
                                log=log_text
                                + f"\n\n--- /workspace check failed ---\n{ws_result.detail}",
                                stats=_build_timestats,
                            )
                        logger.info(
                            f"[build_image]::workspace_check=passed attempt {attempt}: workspace check OK — {ws_result.detail}"
                        )
            except Exception as e:
                logger.error(
                    f"[build_image]::unexpected_error attempt {attempt}: unexpected error during build verification — {str(e)}"
                )

            return BuildResult(success=True, log=log_text, stats=_build_timestats)

        STRONG_INFRA_LOG_PATTERNS = [
            "insufficient UIDs or GIDs available in user namespace",
            "lchown /etc/gshadow: invalid argument",
            "contains several valid graphdrivers",
        ]
        infrastructure_failure = any(p in log_text for p in STRONG_INFRA_LOG_PATTERNS)

        if not infrastructure_failure:
            fb = await self._sandbox.exec(["cat /artifacts/build_feedback.json"])
            if fb.return_code == 0 and fb.stdout and fb.stdout.strip():
                try:
                    fb_data = json.loads(fb.stdout)

                    # Prefer agent_fixable — explicit control signal written by the validator.
                    # Omitted when the validator is uncertain; fall through to allowlist in that case.
                    agent_fixable = fb_data.get("agent_fixable")
                    failure_domain = fb_data.get("failure_domain", "")

                    if agent_fixable is not None:
                        infrastructure_failure = not agent_fixable
                        # Warn when agent_fixable and failure_domain are semantically inconsistent.
                        if agent_fixable and failure_domain == "infra":
                            logger.warning(
                                f"[{self.name}] build_feedback conflict: "
                                f"agent_fixable=true but failure_domain=infra — "
                                f"classifying as non-infra (agent_fixable wins). "
                                f"Review validator prompt."
                            )
                        elif (
                            not agent_fixable
                            and failure_domain
                            and failure_domain != "infra"
                        ):
                            logger.warning(
                                f"[{self.name}] build_feedback conflict: "
                                f"agent_fixable=false but failure_domain={failure_domain!r} — "
                                f"classifying as infra (agent_fixable wins). "
                                f"Review validator prompt."
                            )
                    else:
                        # Legacy fallback: infer from failure_class allowlist.
                        failure_class = (
                            fb_data.get("failure_class")
                            or fb_data.get("failure_reason")
                            or (fb_data.get("failure_details") or {}).get("error_type")
                            or ""
                        )
                        infrastructure_failure = (
                            failure_class in INFRASTRUCTURE_FAILURE_TYPES
                        )

                except (json.JSONDecodeError, ValueError):
                    pass

        return BuildResult(
            success=False,
            log=log_text,
            infrastructure_failure=infrastructure_failure,
            stats=_build_timestats,
        )

    async def _build_apptainer_image(self, attempt: int, context: AgentContext):
        """This builds the apptainer sif from the archive buildah provides"""
        log_path = (
            f"/artifacts/build_logs/apptainer-outer-build-attempt-{attempt:02d}.log"
        )
        remove_exists = await self._sandbox.exec(
            ["rm", "-f", "openenv-validation-docker.tar"],
            cwd="/artifacts/environment",
            timeout=1800,
        )
        if remove_exists.return_code != 0:
            logger.warning(
                f"Docker archive removal failed with error:{remove_exists.stderr}"
            )
        push_cmd = (
            "set -euo pipefail;"
            "buildah push openenv-validation:latest docker-archive:openenv-validation-docker.tar;"
        )
        result = await self._sandbox.exec(
            [push_cmd], cwd="/artifacts/environment", timeout=1800
        )
        if result.return_code != 0:
            return ApptainerBuildResult(
                success=False, log=result.stdout or result.stderr or ""
            )

        build_cmd = (
            "set -euo pipefail;"
            f"apptainer build --fakeroot --force openenv-validation.sif docker-archive://openenv-validation-docker.tar| tee {log_path}"
        )
        result = await self._sandbox.exec(
            [build_cmd], cwd="/artifacts/environment", timeout=1800
        )
        if result.return_code != 0:
            return ApptainerBuildResult(
                success=False,
                log="Running Apptainer build over the buildah image to create the openenv-validation.sif but faced with the error "
                + (result.stdout or result.stderr or ""),
            )
        return ApptainerBuildResult(success=True, log=result.stdout or "")

    async def _check_build_environment(self) -> tuple[bool, str]:
        """Pre-loop preflight: check quality blockers that prevent any useful agent work.

        Only checks binary availability and user-namespace functionality —
        NOT uid_map_too_small, which only blocks image build, not content synthesis.
        Returns (viable, detail).
        """
        for binary, detail in [
            ("buildah", "missing_buildah"),
            ("apptainer", "missing_apptainer"),
            ("unshare", "missing_unshare"),
        ]:
            r = await self._sandbox.exec([f"command -v {binary}"])
            if r.return_code != 0:
                return PreflightCheckResult(viable=False, detail=detail)

        r = await self._sandbox.exec(["unshare -r true"])
        if r.return_code != 0:
            return PreflightCheckResult(viable=False, detail="unshare_test_failed")

        return PreflightCheckResult(viable=True, detail=None)

    async def _write_early_stop_status(
        self,
        stop_reason: str,
        stop_stage: str,
        failure_type: str,
        detail: Optional[str],
        env_failure_streak: int,
    ) -> None:
        """Write early_stop.json and update (or create) manager.json with stop summary."""
        early_stop_data = {
            "early_stop_triggered": True,
            "early_stop_precheck_enabled": self.early_stop_precheck_enabled,
            "early_stop_infra_streak_enabled": self.early_stop_infra_streak_enabled,
            "early_stop_threshold": self.early_stop_threshold,
            "env_failure_streak": env_failure_streak,
            "stop_reason": stop_reason,
            "stop_stage": stop_stage,
            "failure_type": failure_type,
            "detail": detail,
        }
        early_stop_json = json.dumps(early_stop_data, indent=2, ensure_ascii=False)
        await self._sandbox.exec(
            [
                f"printf '%s' {shlex.quote(early_stop_json)} > /artifacts/status/early_stop.json"
            ]
        )

        manager_data: dict = {}
        r = await self._sandbox.exec(["cat /artifacts/status/manager.json"])
        if r.return_code == 0 and r.stdout and r.stdout.strip():
            try:
                manager_data = json.loads(r.stdout)
            except (json.JSONDecodeError, ValueError):
                pass

        if "status" not in manager_data:
            manager_data["status"] = "early_stop"

        manager_data.update(
            {
                "early_stop_triggered": True,
                "stop_reason": stop_reason,
                "stop_stage": stop_stage,
                "failure_type": failure_type,
                "detail": detail,
                "early_stop_detail": "see /artifacts/status/early_stop.json",
            }
        )
        manager_json = json.dumps(manager_data, indent=2, ensure_ascii=False)
        await self._sandbox.exec(
            [
                f"printf '%s' {shlex.quote(manager_json)} > /artifacts/status/manager.json"
            ]
        )
        logger.info(
            f"[{self.name}] early stop: reason={stop_reason} stage={stop_stage} "
            f"detail={detail} streak={env_failure_streak}"
        )

    async def _check_workspace_in_image(self, container: str) -> "CheckWorkspaceResult":
        """
        Verify /workspace inside the Apptainer sandbox is non-empty.
        """
        check_cmd = (
            f"apptainer exec --fakeroot --no-eval --containall --no-home --writable "
            f"--env DEBIAN_FRONTEND=noninteractive --env FAKEROOTDONTTRYCHOWN=1 "
            f"{container} bash -c '"
            # Check existence
            "if [ ! -d /workspace ]; then echo WORKSPACE_STATUS=missing; exit 1; fi; "
            # Count top-level entries
            'count=$(find /workspace -maxdepth 1 -mindepth 1 -name "[!.]*" | wc -l); '
            "echo WORKSPACE_COUNT=$count; "
            # List up to 15 entries for the log
            'find /workspace -maxdepth 1 -mindepth 1 -name "[!.]*" | sort | head -15'
            "'"
        )
        result = await self._sandbox.exec([check_cmd], timeout=120)
        output = (result.stdout or "").strip()

        if result.return_code != 0 or "WORKSPACE_STATUS=missing" in output:
            return CheckWorkspaceResult(
                success=False,
                detail="/workspace directory is missing inside the built image",
            )

        count_line = [
            ln for ln in output.splitlines() if ln.startswith("WORKSPACE_COUNT=")
        ]
        if not count_line:
            return CheckWorkspaceResult(
                success=False,
                detail=(
                    f"could not determine /workspace entry count; "
                    f"rc={result.return_code} output={output[:300]!r}"
                ),
            )

        try:
            count = int(count_line[0].split("=", 1)[1].strip())
        except ValueError:
            return CheckWorkspaceResult(
                success=False, detail=f"malformed WORKSPACE_COUNT line: {count_line!r}"
            )

        listing = "\n".join(
            ln for ln in output.splitlines() if not ln.startswith("WORKSPACE_COUNT=")
        )

        if count == 0:
            return CheckWorkspaceResult(
                success=False,
                detail=(
                    "/workspace exists but is empty — repo_setup.sh may have failed "
                    "to clone or materialise the repository during image build."
                ),
            )

        return CheckWorkspaceResult(
            success=True, detail=f"{count} top-level entries found:\n{listing}"
        )

    async def _build_apptainer_container(self):
        """This method creates the apptainer container from the sif file"""
        build_cmd = (
            "set -euo pipefail;"
            "rm -rf /tmp/swe_built_sandbox;"
            f"apptainer build --fakeroot --sandbox /tmp/swe_built_sandbox openenv-validation.sif"
        )
        result = await self._sandbox.exec(
            [build_cmd], cwd="/artifacts/environment", timeout=1800
        )
        if result.return_code != 0:
            return ApptainerBuildResult(
                success=False, container=None, log=result.stdout or result.stderr or ""
            )

        return ApptainerBuildResult(
            success=True,
            container="/tmp/swe_built_sandbox",
            log=result.stdout or result.stderr or "",
        )

    async def _get_required_verfier_files(self):
        """This method returns the required verifier files"""
        _DEFAULT_VERIFIER_PATHS = [
            "/artifacts/evaluation/*",
            "/artifacts/evaluation/eval.sh",
        ]
        analyst_feedback_raw = await self._sandbox.exec(
            ["cat /artifacts/analysis_feedback.json 2>/dev/null"]
        )
        analyst_feedback = {}
        if (
            analyst_feedback_raw.return_code == 0
            and analyst_feedback_raw.stdout.strip()
        ):
            try:
                analyst_feedback = json.loads(analyst_feedback_raw.stdout)
            except json.JSONDecodeError:
                return _DEFAULT_VERIFIER_PATHS
        required_files = (
            analyst_feedback.get("verifier_alignment", {})
            .get("required_files_audit", {})
            .get("suggested_required_verifier_files")
        )
        if required_files:
            return [
                (
                    f"/artifacts/evaluation/{i}"
                    if not i.startswith("/artifacts/evaluation/")
                    else i
                )
                for i in required_files
            ]
        else:
            return _DEFAULT_VERIFIER_PATHS

    @staticmethod
    def _check_eval_output_quality(output: str, label: str) -> list[str]:
        """Check that eval.sh output contains recognizable test-runner signals."""
        issues: list[str] = []
        start = output.find(">>>>> Start Test Output")
        end = output.find(">>>>> End Test Output")
        if start == -1 or end == -1 or end <= start:
            issues.append(
                f"{label}: test output delimiters(>>>>> Start Test Output,>>>>> End Test Output) missing or malformed"
            )
            return issues
        body = output[start + len(">>>>> Start Test Output") : end]
        body_lines = [ln for ln in body.splitlines() if ln.strip()]
        if len(body_lines) < 2:
            issues.append(f"{label}: test output body empty (< 2 non-blank lines)")
        if not TEST_SIGNAL_RE.search(body):
            issues.append(
                f"{label}: no recognizable test-runner signal between markers(>>>>> Start Test Output,>>>>> End Test Output) "
                "(expected passed/failed/error/etc)"
            )
        return issues

    async def _verify_eval(self, attempt: int, context: AgentContext) -> VerifyResult:
        """Run eval.sh twice: testOnly (buggy /workspace) and testWithFix (patched). It uses the apptainer image created by the _build_apptainer_container()"""
        issues = []
        build_image = await self._build_apptainer_container()
        if not build_image.success:
            return VerifyResult(
                success=False,
                issues=["failed to prepare runtime image for verification"],
            )
        # prepare eval_cmds
        eval_prep_cmd = [
            "mkdir -p /artifacts/verify_logs",
            "&&",
            "chmod +x /artifacts/evaluation/eval.sh",
            "&&",
            f"mkdir -p {build_image.container}/tests",
        ]
        eval_prep_result = await self._sandbox.exec(
            eval_prep_cmd,
            timeout=600,
        )
        if eval_prep_result.return_code != 0:
            logger.warning(
                f"[{self.name}] eval verification failure: {eval_prep_result.stderr}"
            )

            return VerifyResult(
                success=False,
                issues=[
                    f"failed to setup the tests folder in verification container, failed due to error {eval_prep_result.stderr}"
                ],
            )

        # check the required_paths from the
        eval_files = await self._get_required_verfier_files()

        if eval_files:
            for src in eval_files:
                test_copy_cmd = []
                rel = os.path.relpath(src, "/artifacts/evaluation/")
                dst_parent = Path(rel).parent
                if dst_parent != Path("."):
                    test_copy_cmd.append(
                        f"mkdir -p {shlex.quote(f'{build_image.container}/tests/' + str(dst_parent))} && "
                    )

                test_copy_cmd += [
                    f"cp {shlex.quote(src)} {shlex.quote(f'{build_image.container}/tests/' + rel)}"
                ]
                test_copy_result = await self._sandbox.exec(
                    test_copy_cmd,
                    timeout=600,
                )
                if test_copy_result.return_code != 0:
                    logger.warning(
                        f"[{self.name}] eval verification failure: cmd::{test_copy_cmd} and error {test_copy_result.stderr}"
                    )

                    return VerifyResult(
                        success=False,
                        issues=[
                            f"verifier setup failed: could not copy /artifacts/evaluation/ into the sandbox /tests/ mount "
                            f"Ensure eval-builder produced all required verifier assets. "
                            f"stderr: {test_copy_result.stderr or '(empty)'}"
                        ],
                    )

        # testOnly path
        test_only_log = f"/artifacts/verify_logs/test_only.log"
        test_only_cmd = [
            f"apptainer  exec --fakeroot --no-eval --containall --no-home --writable  --env DEBIAN_FRONTEND=noninteractive --env FAKEROOTDONTTRYCHOWN=1  {build_image.container} bash -c 'cd /workspace && chmod +x /tests/eval.sh && /tests/eval.sh' 2>&1"
            f"| tee {test_only_log}",
        ]
        base_result = await self._sandbox.exec(
            test_only_cmd,
            timeout=600,
        )
        base_output = base_result.stdout or ""
        base_exit_code = self.__class__._parse_eval_out_marker(base_output)
        issues.extend(
            self.__class__._check_eval_output_quality(base_output, "testOnly")
        )

        # testWithFix — apply patch, run, revert
        test_with_fix_log = f"/artifacts/verify_logs/test_with_fix.log"
        fix_cmd = [
            f"mkdir -p {build_image.container}/tasks",
            "&&",
            f"cp -r /tasks/fix.patch {build_image.container}/tasks/",
            "&&",
            f"apptainer  exec --fakeroot --no-eval --containall --no-home --writable  --env DEBIAN_FRONTEND=noninteractive --env FAKEROOTDONTTRYCHOWN=1  {build_image.container} bash -c 'cd /workspace && git apply --whitespace=nowarn /tasks/fix.patch && chmod +x /tests/eval.sh && /tests/eval.sh' 2>&1",
            f"| tee {test_with_fix_log}",
        ]
        fixed_result = await self._sandbox.exec(
            fix_cmd,
            timeout=600,
        )
        fixed_output = fixed_result.stdout or ""
        fixed_exit_code = self.__class__._parse_eval_out_marker(fixed_output)
        issues.extend(
            self.__class__._check_eval_output_quality(fixed_output, "testWithFix")
        )

        # Determine success
        if base_exit_code is None:
            issues.append("testOnly did not emit OPENENV_EXIT_CODE")
        elif base_exit_code == 0:
            issues.append(
                "testOnly unexpectedly passed (expected non-zero on buggy code)"
            )

        if fixed_exit_code is None:
            issues.append("testWithFix did not emit OPENENV_EXIT_CODE")
        elif fixed_exit_code != 0:
            issues.append(
                f"testWithFix failed with OPENENV_EXIT_CODE={fixed_exit_code} (expected 0)"
            )

        return VerifyResult(
            success=not issues,
            base_exit_code=base_exit_code,
            fixed_exit_code=fixed_exit_code,
            base_output=base_output,
            fixed_output=fixed_output,
            issues=issues,
        )

    async def _write_verify_feedback(self, verify: VerifyResult) -> None:
        """Write /artifacts/verify_feedback.json so openenv-manager can consume it."""
        payload = {
            "test_only_exit_code": verify.base_exit_code,
            "test_with_fix_exit_code": verify.fixed_exit_code,
            "is_success": verify.success,
            "issues": verify.issues,
            "notes": "outer orchestrator image-level verification",
        }
        write_cmd = [
            f"mkdir -p /artifacts/verify_logs && "
            f"printf '%s' {shlex.quote(json.dumps(payload, indent=2))} > /artifacts/verify_feedback.json",
        ]
        await self._sandbox.exec(write_cmd)

    async def _export_harbor_task(self, context: AgentContext) -> None:
        """
        Write a Harbor-format task bundle to /artifacts/harbor_task/.

        Reads task metadata from /tasks/<task_id>/task_input.json and synthesized artifacts
        from /artifacts/. Generates task.toml, instruction.md, test.sh, and solve.sh
        using harbor_format.py. Copies Dockerfile, eval.sh, setup_runtime.sh, fix.patch,
        and optional test assets into the Harbor layout.

        Gated on artifact presence — skips silently if required artifacts are missing.
        Called at both terminal return points (success and failure).
        """
        logger.info(f"[{self.name}] _export_harbor_task: checking artifact gate")

        # --- Artifact gate: all required files must exist ---
        required_checks = " && ".join(
            f"test -f /artifacts/{p}" for p in HARBOR_REQUIRED_ARTIFACTS
        )
        gate_result = await self._sandbox.exec(
            [f"({required_checks}) && echo OK || echo MISSING"]
        )
        if gate_result.stdout.strip() != "OK":
            logger.warning(
                f"[{self.name}] _export_harbor_task: skipping — required artifacts incomplete "
                f"(need: {HARBOR_REQUIRED_ARTIFACTS})"
            )
            return

        # At least one verifier asset must exist
        verifier_checks = " || ".join(
            f"test -{'d' if p.endswith('tests') else 'f'} /artifacts/{p}"
            for p in HARBOR_VERIFIER_ASSETS
        )
        verifier_result = await self._sandbox.exec(
            [f"({verifier_checks}) && echo OK || echo MISSING"]
        )
        if verifier_result.stdout.strip() != "OK":
            logger.warning(
                f"[{self.name}] _export_harbor_task: skipping — no verifier asset found "
                f"(need one of: {HARBOR_VERIFIER_ASSETS})"
            )
            return

        logger.info(f"[{self.name}] _export_harbor_task: gate passed, exporting")

        # --- Read task_input.json ---
        ti_result = await self._sandbox.exec(
            ["cat", f"{context.task_dir}/task_input.json"]
        )
        if ti_result.return_code != 0:
            logger.warning(
                f"[{self.name}] _export_harbor_task: cannot read task_input.json, skipping"
            )
            return
        try:
            task_input = json.loads(ti_result.stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                f"[{self.name}] _export_harbor_task: malformed task_input.json: {exc}, skipping"
            )
            return

        # --- Read exploration_report.json for runtime_family ---
        runtime_family = None
        er_result = await self._sandbox.exec(
            ["cat", "/artifacts/environment/exploration_report.json"]
        )
        if er_result.return_code == 0:
            try:
                er_data = json.loads(er_result.stdout)
                runtime_family = er_data.get("runtime_family") or None
            except (json.JSONDecodeError, ValueError):
                pass

        # --- Create directory structure ---
        await self._sandbox.exec(
            [
                "mkdir -p /artifacts/harbor_task/environment "
                "/artifacts/harbor_task/solution "
                "/artifacts/harbor_task/tests",
            ]
        )

        # --- Copy required files — each failure surfaces and aborts the export ---
        required_copies = (
            "cp /artifacts/environment/Dockerfile.final /artifacts/harbor_task/environment/Dockerfile"
            " && cp /artifacts/environment/repo_setup.sh /artifacts/harbor_task/environment/repo_setup.sh"
            " && cp /artifacts/environment/setup_runtime.sh /artifacts/harbor_task/environment/setup_runtime.sh"
            " && cp /artifacts/evaluation/eval.sh /artifacts/harbor_task/tests/eval.sh"
            # " && cp /artifacts/environment/setup_runtime.sh /artifacts/harbor_task/tests/setup_runtime.sh"
            " && cp /tasks/fix.patch /artifacts/harbor_task/solution/fix.patch"
        )
        req_result = await self._sandbox.exec([required_copies])
        if req_result.return_code != 0:
            logger.error(
                f"[{self.name}] _export_harbor_task: required copy failed "
                f"(rc={req_result.return_code}), aborting Harbor export"
            )
            return

        # --- Copy optional verifier files — respects required_verifier_files when declared ---
        required_verifier_files = await self._get_required_verfier_files()

        if required_verifier_files:
            # only declared files (eval.sh already copied in required_copies)
            for src in required_verifier_files:
                if "eval.sh" in src:
                    continue
                eval_copy_cmd = []
                rel = os.path.relpath(src, "/artifacts/evaluation/")
                dst_parent = Path(rel).parent
                if dst_parent != Path("."):
                    eval_copy_cmd.append(
                        f"mkdir -p {shlex.quote('/artifacts/harbor_task/tests/' + str(dst_parent))} && "
                    )
                eval_copy_cmd += [
                    f"cp {shlex.quote(src)} {shlex.quote('/artifacts/harbor_task/tests/'+rel)} 2>/dev/null || true"
                ]
                await self._sandbox.exec(eval_copy_cmd)
        else:
            # Fallback: copy test.patch
            await self._sandbox.exec(
                [
                    "cp /artifacts/evaluation/test.patch "
                    "/artifacts/harbor_task/tests/test.patch 2>/dev/null || true",
                ]
            )
            await self._sandbox.exec(
                [
                    "mkdir -p /artifacts/harbor_task/tests/tests &&"
                    "tar --exclude='node_modules' --exclude='target' --exclude='build' "
                    "--exclude='dist' --exclude='__pycache__' --exclude='.venv' "
                    "--exclude='.pytest_cache' --exclude='*.pyc' --exclude='*.class' "
                    "-c -C /artifacts/evaluation/tests/ . | tar -x -C /artifacts/harbor_task/tests/tests/ 2>/dev/null || true"
                ]
            )
        # tests/test.sh
        await self._sandbox.exec(
            [
                f"printf '%s' {shlex.quote(_TEST_SH)} > /artifacts/harbor_task/tests/test.sh && "
                f"chmod 755 /artifacts/harbor_task/tests/test.sh"
            ]
        )

        # solution/solve.sh
        await self._sandbox.exec(
            [
                f"printf '%s' {shlex.quote(_SOLVE_SH)} > /artifacts/harbor_task/solution/solve.sh && "
                f"chmod 755 /artifacts/harbor_task/solution/solve.sh"
            ]
        )

        # instruction.md — use tuned instruction if a better version was selected
        instruction_content = build_instruction_md(task_input)
        tuning_raw = await self._sandbox.exec(
            ["cat /artifacts/instructions/instruction_tuning_decision.json 2>/dev/null"]
        )
        if tuning_raw.return_code == 0 and tuning_raw.stdout.strip():
            try:
                tuning = json.loads(tuning_raw.stdout)
                if tuning.get("selected_version", 0) > 0:
                    cand_raw = await self._sandbox.exec(
                        [f"cat {shlex.quote(tuning['selected_path'])} 2>/dev/null"]
                    )
                    if cand_raw.stdout.strip():
                        instruction_content = cand_raw.stdout.strip("") + "\n"
                        logger.info(
                            f"[{self.name}] using tuned instruction v{tuning['selected_version']} "
                            f"(score {tuning['selected_score']:.2f} "
                            f"vs baseline {tuning['baseline_score']:.2f})"
                        )
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        await self._sandbox.exec(
            [
                f"printf '%s' {shlex.quote(instruction_content)} > /artifacts/harbor_task/instruction.md"
            ]
        )

        # task.toml — docker_image is absent. The built image stays in the sandbox's local
        # store; publishing it to a registry is left to whoever runs this.
        toml_content = build_task_toml(
            task_input, runtime_family, pushed_image_ref=None,
            total_turns=self._run_stats["total_turns"],
        )
        await self._sandbox.exec(
            [
                f"printf '%s' {shlex.quote(toml_content)} > /artifacts/harbor_task/task.toml"
            ]
        )
        logger.info(
            f"[{self.name}] _export_harbor_task: Harbor bundle written to "
            f"/artifacts/harbor_task/ (task_id={task_input.get('task_id', '?')})"
        )

    async def _run_solver_judge(
        self,
        task_dir: str,
        run_dir: str,
        task_log_dir: str,
        inst_path: str = "/tasks/issue.md",
        traj_analysis_path="/artifacts/analysis_report",
        traj_analysis_status_path="/artifacts/status",
    ) -> None:
        """This is just a helper method to be used with the running the solver judge"""
        build_image = await self._build_apptainer_container()
        if not build_image.success:
            logger.error(
                "failed to prepare the apptainer container to run the solver agent"
            )
            return -1

        # Creating the required folders
        await self._sandbox.exec(
            [
                f"mkdir -p {build_image.container}/tasks;",
                f"mkdir -p {build_image.container}/artifacts;",
            ]
        )
        # Just copy required files
        await self._sandbox.exec(
            [
                f"cp {inst_path} {build_image.container}/tasks/instruction.md 2>/dev/null || true",
            ]
        )
        await self._sandbox.exec(
            [
                f"cp /tasks/fix.patch {build_image.container}/artifacts/fix.patch 2>/dev/null || true",
            ]
        )

        # Install opencode, copied from the agentdist opencode setup
        check = await self._sandbox.exec(
            [
                f"apptainer exec --fakeroot --no-eval --containall --no-home --writable  --env DEBIAN_FRONTEND=noninteractive --env FAKEROOTDONTTRYCHOWN=1 {build_image.container} ",
                "command -v opencode 2>/dev/null",
                "&&",
                "echo ok || echo missing",
            ]
        )
        if "missing" in (check.stdout or ""):
            if self.opencode_predownloaded_install_path:
                _create_dir = await self._sandbox.exec(
                    [f"mkdir -p {build_image.container}/.download_artifacts"]
                )
                async with self._log_timing_stats(
                    self._run_stats["analyzer_builder"], "opencode_install"
                ):
                    install = await self._sandbox.exec(
                        [
                            f"apptainer exec --fakeroot --no-eval --containall --no-home --writable "
                            f"--bind {self.opencode_predownloaded_install_path}:/.download_artifacts "
                            f"--env DEBIAN_FRONTEND=noninteractive --env FAKEROOTDONTTRYCHOWN=1 "
                            f"{build_image.container} bash -c /.download_artifacts/install_opencode.sh"
                        ],
                        timeout=300,
                    )
                if install.return_code != 0:
                    logger.warning(
                        f"[{self.name}] opencode install failed "
                        f"(rc={install.return_code}); skipping analyze step\n{install.stdout}"
                    )
                    return -1
            # Fallback installtion method if opencode pre-downloaded doesn't exist
            else:
                logger.info(
                    f"[{self.name}] installing opencode in sandbox via curl install script"
                )
                install_script = (
                    "which curl || ("
                    "  apt-get install -y --no-install-recommends curl 2>/dev/null ||"
                    "  yum install -y curl 2>/dev/null ||"
                    "  apk add --no-cache curl 2>/dev/null"
                    ") && "
                    "curl -fsSL https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/install"
                    " | VERSION=v1.4.6 bash && "
                    "ln -sf $HOME/.opencode/bin/opencode /usr/local/bin/opencode"
                )
                async with self._log_timing_stats(
                    self._run_stats["analyzer_builder"], "opencode_install"
                ):
                    install = await self._sandbox.exec(
                        [
                            "apptainer",
                            "exec",
                            "--fakeroot",
                            "--no-eval",
                            "--containall",
                            "--no-home",
                            "--writable",
                            f"{build_image.container}",
                            "bash",
                            "-c",
                            f"{shlex.quote(install_script)}",
                        ],
                        timeout=300,
                    )
                if install.return_code != 0:
                    logger.warning(
                        f"[{self.name}] opencode install in sandbox failed (rc={install.return_code}); "
                        "skipping analyze step"
                    )
                    return -1

        # check opencode config content variable is defined
        opencode_config_content = None
        check_config = await self._sandbox.exec(
            ['echo "$OPENCODE_CONFIG_CONTENT" || echo MISSING']
        )
        if check_config.stdout.strip() == "MISSING":
            logger.warning(
                f"[{self.name}] OPENCODE_CONFIG_CONTENT is not set in the sandbox environment; "
                "opencode may not function correctly. Check the install method and environment variables."
            )
        else:
            opencode_config_content = check_config.stdout.strip()
            try:
                opencode_config_content = json.dumps(
                    json.loads(opencode_config_content)
                )
            except json.JSONDecodeError:
                logger.warning(
                    f"[{self.name}] Unable to parse the OPENCODE_CONFIG_CONTENT in _analyze_builder stage: {opencode_config_content}"
                )

        # Running the agent
        solver_out = f"{task_log_dir}/solver-run.out"
        opencode_config_env = (
            f"--env OPENCODE_CONFIG_CONTENT={shlex.quote(str(opencode_config_content))}"
            if opencode_config_content
            else ""
        )
        solver_cmd = (
            "apptainer exec --fakeroot "
            "--no-eval --containall --no-home --writable "
            f"--env DEBIAN_FRONTEND=noninteractive --env FAKEROOTDONTTRYCHOWN=1 {opencode_config_env} {build_image.container} "
            "bash -c 'cd /workspace && opencode run --format json -- \"$(cat /tasks/instruction.md)\" 2>&1' "
            f"| tee {solver_out}"
        )
        async with self._log_timing_stats(
            self._run_stats["analyzer_builder"], "solver_run"
        ):
            solver_result = await self._sandbox.exec(
                [solver_cmd], timeout=self.analyze_run_time_budget
            )
        logger.info(f"[{self.name}] solver exited rc={solver_result.return_code}")

        # oracle test validation for the solver agent validation
        test_verifier_log = f"{traj_analysis_path}/oracle_verifier.log"
        oracle_setup_cmds = [
            f"mkdir -p {build_image.container}/tests &&",
            f"chmod +x {build_image.container}/tests &&",
            f"cp -r /artifacts/evaluation/* {build_image.container}/tests/",
        ]
        oracle_setup_result = await self._sandbox.exec(oracle_setup_cmds)
        if oracle_setup_result.return_code != 0:
            logger.error(
                f"[{self.name}] oracle setup failed (rc={oracle_setup_result.return_code})(error:{self.__class__._tail(oracle_setup_result.stderr,40)}); skipping trajectory export"
            )
            return -1

        oracle_run = await self._sandbox.exec(
            [
                f"apptainer  exec --fakeroot --no-eval --containall --no-home --writable  --env DEBIAN_FRONTEND=noninteractive --env FAKEROOTDONTTRYCHOWN=1  {build_image.container} bash -c 'cd /workspace && chmod +x /tests/eval.sh && /tests/eval.sh' 2>&1"
                f"| tee {test_verifier_log}"
            ]
        )

        if oracle_run.return_code != 0:
            logger.error(
                f"[{self.name}] oracle run failed (rc={oracle_run.return_code})(error:{self.__class__._tail(oracle_run.stderr,40)}); skipping trajectory export"
            )
            return -1

        # get the trajectory of sample run
        session_list_cmd = (
            f"apptainer exec --fakeroot --no-eval --containall --no-home --writable {opencode_config_env} {build_image.container} "
            "bash -c 'cd /workspace && opencode session list --format json 2>/dev/null || echo []'"
        )
        session_result = await self._sandbox.exec([session_list_cmd])
        sessions: list = []
        try:
            sessions = json.loads(session_result.stdout.strip() or "[]")
        except (json.JSONDecodeError, TypeError):
            pass

        solver_agent_trajectory_path = (
            f"{traj_analysis_path}/solver_run_trajectory.json"
        )
        if sessions and isinstance(sessions, list):
            solver_session_id = sessions[-1].get("id") if sessions else None
            if solver_session_id:
                export_cmd = (
                    f"apptainer exec --fakeroot --no-eval --containall --no-home --writable {opencode_config_env} {build_image.container} "
                    f"bash -c 'cd /workspace && opencode export {solver_session_id} > /artifacts/solver_run_trajectory.json 2>&1'"
                )
                export_result = await self._sandbox.exec([export_cmd], timeout=120)
                if export_result.return_code == 0:
                    logger.info(
                        f"[{self.name}] solver trajectory saved to {solver_agent_trajectory_path}"
                    )
                else:
                    logger.warning(f"[{self.name}] solver trajectory export failed")
                    return
        else:
            logger.warning(
                f"[{self.name}] no solver sessions found; skipping trajectory export"
            )

        copy_result = await self._sandbox.exec(
            [
                f"cp {build_image.container}/artifacts/solver_run_trajectory.json {solver_agent_trajectory_path} 2>/dev/null"
            ]
        )
        if copy_result.return_code != 0:
            logger.warning(
                f"[{self.name}] failed to copy solver trajectory for analysis report"
            )
            return -1
        # Run openenv-trajectory-judge agent
        judge_out = f"{task_log_dir}/trajectory-judge.out"
        judge_instruction = (
            "Evaluate the solver trajectory for this task. "
            f"Inputs are at {traj_analysis_path}/solver_run_trajectory.json (solver trajectory), {traj_analysis_path}/oracle_verifier.log (oracle verifier run log) "
            f"/tasks/fix.patch (solution diff), /artifacts/environment/exploration_report.json (exploration report), /artifacts/evaluation/eval.sh (oracle verifier script) and {inst_path} (task instruction) "
            f"Write your evaluation report to {traj_analysis_path}/trajectory_evaluation.json "
            f"and status file to {traj_analysis_status_path}/trajectory_judge.json."
        )
        if solver_result.return_code != 0 and "Timeout" in solver_result.stderr:
            judge_instruction += f" The solver agent run time budget capped at {self.analyze_run_time_budget} seconds. so the trajectory may be incomplete."

        # Snapshot the sessions
        async with self._log_timing_stats(
            self._run_stats["analyzer_builder"], "trajectory_snapshot_sessions"
        ):
            pre_session_ids = await self._snapshot_sessions(run_dir)
        judge_model = (
            f"--model {self.agent_small_model}" if self.agent_small_model else ""
        )
        judge_cmd = (
            f"opencode run {judge_model} --agent openenv-trajectory-judge --format json "
            f"-- {shlex.quote(judge_instruction)} "
            f"> {judge_out} 2>&1"
        )
        async with self._log_timing_stats(
            self._run_stats["analyzer_builder"], "trajectory_judge"
        ):
            judge_result = await self._sandbox.exec(
                [judge_cmd], cwd=run_dir, timeout=600
            )
        if judge_result.return_code != 0:
            logger.warning(
                f"[{self.name}] trajectory judge failed (rc={judge_result.return_code})"
            )
        else:
            logger.info(f"[{self.name}] trajectory judge completed successfully")

        # collect the trajectory
        async with self._log_timing_stats(
            self._run_stats["analyzer_builder"], "collect_turn_trajectories"
        ):
            turn_trajectory = await self._collect_turn_trajectories(
                100,
                task_dir,
                pre_session_ids,
                run_dir,
                agent_name="openenv-trajectory-judge",
            )
        return 0

    async def _analyze_builder(self, task_dir: str, run_dir: str) -> None:
        """Run a solver agent inside the built Apptainer sandbox, then evaluate the resulting trajectory with openenv-trajectory-judge. Log-and-save only."""
        logger.info(f"[{self.name}] _analyze_builder: starting solver + judge run")
        traj_analysis_path = "/artifacts/analysis_report"
        await self._sandbox.exec(
            [
                f"mkdir -p {traj_analysis_path};",
            ]
        )
        result = await self._run_solver_judge(
            task_dir=task_dir,
            run_dir=run_dir,
            task_log_dir=f"{task_dir}/logs",
            inst_path="/tasks/issue.md",
            traj_analysis_path=traj_analysis_path,
            traj_analysis_status_path="/artifacts/status",
        )

        if result != 0:
            return

        # Post-judge - as we divided the trajectory collection into two parts (pre-judge and post-judge), we can do some analysis and decision making before deciding whether to run the instruction tuner. This is the trajectory decision step, which reads the judge's evaluation and decides whether instruction tuning is needed, then runs the tuner if so.
        async with self._log_timing_stats(
            self._run_stats["analyzer_builder"], "trajectory_decision"
        ):
            await self._write_trajectory_decision()

        if self.instruction_tuning_enabled:
            async with self._log_timing_stats(
                self._run_stats["analyzer_builder"], "instruction_tuning"
            ):
                await self._run_instruction_tuner(task_dir, run_dir)

    async def _write_trajectory_decision(self) -> None:
        """Read trajectory_evaluation.json, compute deterministic decision, write trajectory_decision.json."""
        te_raw = await self._sandbox.exec(
            ["cat /artifacts/analysis_report/trajectory_evaluation.json 2>/dev/null"]
        )
        if te_raw.return_code != 0 or not te_raw.stdout.strip():
            logger.warning(
                f"[{self.name}] trajectory_evaluation.json not found — skipping decision"
            )
            return
        try:
            te = json.loads(te_raw.stdout)
        except json.JSONDecodeError:
            logger.warning(f"[{self.name}] trajectory_evaluation.json parse error")
            return

        decision = compute_trajectory_decision(te)

        if decision.get("score_warnings"):
            logger.warning(
                f"[{self.name}] judge score inconsistencies: {decision['score_warnings']}"
            )

        await self._sandbox.exec(
            [
                f"mkdir -p /artifacts/analysis_report && "
                f"printf '%s' {shlex.quote(json.dumps(decision, indent=2))} "
                f"> /artifacts/analysis_report/trajectory_decision.json"
            ]
        )
        logger.info(
            f"[{self.name}] trajectory_decision: "
            f"filter={decision['filter_label']} "
            f"keep_for_rl={decision['keep_for_rl']} "
            f"score={decision['overall_score']}"
        )

    async def _run_instruction_tuner(self, task_dir: str, run_dir: str) -> None:
        """
        Read trajectory_decision.json. If needs_instruction_tuning is True,
        build instruction tuner request json, invoke openenv-instruction-tuner, run basic static regrex
        safety checks, then call _score_instruction_candidates for high-priority tuning.
        """
        decision_raw = await self._sandbox.exec(
            ["cat /artifacts/analysis_report/trajectory_decision.json 2>/dev/null"]
        )
        if decision_raw.return_code != 0 or not decision_raw.stdout.strip():
            return
        try:
            decision = json.loads(decision_raw.stdout)
        except json.JSONDecodeError:
            return

        if not decision.get("needs_instruction_tuning"):
            logger.info("As judge mentioned no need of instruction tuning, skipping")
            return

        logger.debug(f"[{self.name}] instruction tuning triggered — building request")

        input_file_read = await asyncio.gather(
            self._sandbox.exec(["cat /tasks/issue.md 2>/dev/null"]),
            self._sandbox.exec(
                ["cat /artifacts/environment/exploration_report.json 2>/dev/null"]
            ),
            self._sandbox.exec(
                [
                    "cat /artifacts/analysis_report/trajectory_evaluation.json 2>/dev/null"
                ]
            ),
        )
        issue_text = input_file_read[0].stdout or ""
        expl_report = (
            json.loads(input_file_read[1].stdout)
            if input_file_read[1].stdout.strip()
            else {}
        )
        te = (
            json.loads(input_file_read[2].stdout)
            if input_file_read[2].stdout.strip()
            else {}
        )

        request = build_instruction_request(issue_text, expl_report, te)
        await self._sandbox.exec(
            [
                f"mkdir -p /artifacts/analysis_report /artifacts/instructions && "
                f"printf '%s' {shlex.quote(json.dumps(request, indent=2))} "
                f"> /artifacts/analysis_report/instruction_request.json"
            ]
        )

        tuner_instruction = (
            "Read /artifacts/analysis_report/instruction_request.json and "
            "/tasks/issue.md and produce instruction candidates as directed. "
            "Write /artifacts/instructions/instruction_v1.md and optionally "
            "/artifacts/instructions/instruction_v2.md."
        )
        tuner_out = f"{task_dir}/logs/instruction-tuner.out"
        # Snapshot the sessions
        async with self._log_timing_stats(
            self._run_stats["analyzer_builder"], "instruction_tuner_snapshot_sessions"
        ):
            pre_session_ids = await self._snapshot_sessions(run_dir)
        tuner_model = (
            f"--model {self.agent_small_model}" if self.agent_small_model else ""
        )
        tuner_cmd = (
            f"opencode run {tuner_model} --agent openenv-instruction-tuner --format json "
            f"-- {shlex.quote(tuner_instruction)} "
            f"> {tuner_out} 2>&1"
        )
        async with self._log_timing_stats(
            self._run_stats["analyzer_builder"], "instruction_tuner"
        ):
            tuner_result = await self._sandbox.exec(
                [tuner_cmd], cwd=run_dir, timeout=900
            )
        if tuner_result.return_code != 0:
            logger.warning(
                f"[{self.name}] instruction tuner failed (rc={tuner_result.return_code})"
            )
            return
        else:
            logger.info(f"[{self.name}] instruction tuner run completed")

        # collect the trajectory
        async with self._log_timing_stats(
            self._run_stats["analyzer_builder"],
            "instruction_tunercollect_turn_trajectories",
        ):
            turn_trajectory = await self._collect_turn_trajectories(
                100,
                task_dir,
                pre_session_ids,
                run_dir,
                agent_name="openenv-instruction-tuner",
            )

        # Static instruction checks
        log_entries: list[dict] = []
        for version in [1, 2]:
            cand_raw = await self._sandbox.exec(
                [f"cat /artifacts/instructions/instruction_v{version}.md 2>/dev/null"]
            )
            if cand_raw.return_code != 0 or not cand_raw.stdout.strip():
                continue
            check = candidate_instruction_safety(issue_text, cand_raw.stdout)
            log_entries.append(
                {
                    "version": version,
                    "path": f"/artifacts/instructions/instruction_v{version}.md",
                    "accepted_for_review": check["accepted"],
                    "rejection_reasons": check["rejection_reasons"],
                    "impl_specific": check["impl_specific"],
                    "verifier_leaks": check["verifier_leak"],
                    "added_words": check["added_words"],
                }
            )
            if not check["accepted"]:
                logger.warning(
                    f"[{self.name}] instruction_v{version} failed safety: {check['rejection_reasons']}"
                )

        await self._sandbox.exec(
            [
                f"printf '%s' {shlex.quote(json.dumps({'candidates': log_entries}, indent=2))} "
                f"> /artifacts/instructions/instruction_tuning_check_log.json"
            ]
        )
        accepted = [e for e in log_entries if e["accepted_for_review"]]
        logger.info(
            f"[{self.name}] instruction tuning: {len(log_entries)} candidate(s), "
            f"{len(accepted)} passed safety"
        )

        if self.instruction_tuner_run_check:
            # Score candidates if high-priority and any passed safety
            if accepted and decision.get("instruction_tuning_priority") == "high":
                async with self._log_timing_stats(
                    self._run_stats["analyzer_builder"],
                    "instruction_tuner_select_candidates",
                ):
                    await self._select_instruction_candidates(
                        task_dir, run_dir, accepted, baseline_decision=decision
                    )

    async def _select_instruction_candidates(
        self,
        task_dir: str,
        run_dir: str,
        candidates: list[dict],
        baseline_decision: dict,
    ) -> None:
        """
        Rerun solver + oracle + judge for each safe candidate instruction.
        Compare overall_score to baseline. Write instruction_tuning_result.json
        with the winning version (candidate must beat baseline by > 0.5).
        """

        build_image = await self._build_apptainer_container()
        if not build_image.success:
            return

        baseline_score = baseline_decision.get("overall_score", 0.0)
        best: dict = {"version": 0, "score": baseline_score, "path": "/tasks/issue.md"}

        for cand in candidates:
            version = cand["version"]
            cand_path = cand["path"]
            inst_log_path = f"/artifacts/instructions/rerun/instruction_v{version}"
            task_log_dir = f"{inst_log_path}/logs"
            traj_analysis_path = f"{inst_log_path}/analysis_report"
            dir_create_result = await self._sandbox.exec(
                [
                    f"mkdir -p {inst_log_path};",
                    f"mkdir -p {task_log_dir};" f"mkdir -p {traj_analysis_path};",
                ]
            )
            if dir_create_result.return_code != 0:
                logger.warning(
                    f"[{self.name}] instruction tuning {version} rerun : prep failure"
                )
                continue

            result = await self._run_solver_judge(
                task_dir=task_dir,
                run_dir=run_dir,
                task_log_dir=task_log_dir,
                inst_path=cand_path,
                traj_analysis_path=traj_analysis_path,
                traj_analysis_status_path=inst_log_path,
            )
            if result != 0:
                logger.warning(
                    f"[{self.name}] instruction tuning {version} rerun : judge run failure"
                )
                continue
            te_path = f"{traj_analysis_path}/trajectory_evaluation.json"
            # Compute deterministic decision for candidate
            te_raw = await self._sandbox.exec(
                [f"cat {shlex.quote(te_path)} 2>/dev/null"]
            )
            if te_raw.return_code != 0 or not te_raw.stdout.strip():
                continue
            try:
                te = json.loads(te_raw.stdout)
            except json.JSONDecodeError:
                continue

            cand_decision = compute_trajectory_decision(te)
            cand_score = cand_decision.get("overall_score", 0.0)

            await self._sandbox.exec(
                [
                    f"printf '%s' {shlex.quote(json.dumps(cand_decision, indent=2))} "
                    f"> {inst_log_path}/trajectory_decision.json"
                ]
            )
            logger.info(
                f"[{self.name}] instruction_v{version}: "
                f"score={cand_score:.2f} vs baseline={baseline_score:.2f}"
            )

            # candidate win if overall > base
            if cand_score > best["score"] + 0.5:
                best = {"version": version, "score": cand_score, "path": cand_path}

        result = {
            "selected_version": best["version"],
            "selected_path": best["path"],
            "selected_score": best["score"],
            "baseline_score": baseline_score,
            "selection_reason": (
                "candidate_improvement" if best["version"] > 0 else "baseline_preferred"
            ),
        }
        await self._sandbox.exec(
            [
                f"printf '%s' {shlex.quote(json.dumps(result, indent=2))} "
                f"> /artifacts/instructions/instruction_tuning_decision.json"
            ]
        )
        logger.info(
            f"[{self.name}] instruction selection: v{best['version']} "
            f"score={best['score']:.2f} vs baseline={baseline_score:.2f}"
        )

    def _construct_prompt(
        self,
        base_prompt: str,
        heading: str,
        skip_workers: list[str],
        target_worker: str,
        log_tail: str = "",
    ) -> str:
        """
            Compose a remediation prompt that gives the manager targeted routing
            instructions so it only re-invokes the targeted worker(s) that need fixing,
        rather than re-running the entire pipeline from scratch.
        """
        lines = [
            base_prompt,
            "",
            "---",
            "Remediation context (from external orchestrator):",
            heading,
            "",
            "Routing instructions:",
        ]

        lines += [
            "- Continue from the current /workspace, /workspace_fixed, /artifacts, /tasks state.",
            "- Update artifacts in place. Do not restart from scratch unless a full reset is strictly required.",
            "- You are running `openenv-manager`; explicitly invoke the corresponding worker or workers needed to repair the affected artifacts."
            "- Do not treat any worker as permanently skippable. If an upstream artifact, dependency decision, runtime script, verifier asset, or packaging file changed, rerun every worker that depends on that change even if it was previously skipped."
            "- Update /artifacts/status/manager.json with the final outcome when done.",
        ]

        if skip_workers:
            lines.append(
                f"- Do NOT re-invoke: `{'`, `'.join(skip_workers)}`. "
                "Their artifacts are already complete and correct. Unless your fix changes their dependent inputs."
            )
        if target_worker:
            lines.append(
                f"- Re-invoke: `{target_worker}` to fix the issue described above."
            )

        if log_tail:
            trimmed = log_tail[-6000:] if len(log_tail) > 6000 else log_tail
            lines += ["", "Relevant logs:", "```text", trimmed, "```"]
        return "\n".join(lines).strip() + "\n"

    def _construct_artifact_feedback(
        self, base_prompt: str, audit: ArtifactAudit, agent_output: str
    ) -> str:
        passing = [
            w for w, s in audit.status_summary.items() if s.lower() in SUCCESS_STATUSES
        ]
        failing = [
            w
            for w in STATUS_WORKERS
            if w not in passing
            and audit.status_summary.get(w, "missing").lower() not in SUCCESS_STATUSES
        ]
        target = (
            f"openenv-{failing[0].replace('_', '-')}"
            if failing and len(failing) == 1
            else "openenv-manager"
        )

        details: list[str] = []
        if audit.missing:
            details.append("Missing artifacts: " + ", ".join(audit.missing))
        if audit.blocking_messages:
            details.append("Blocking statuses: " + ", ".join(audit.blocking_messages))
        if audit.manager_notes:
            details.append(f"Manager notes: {audit.manager_notes}")

        heading = (
            "Previous turn incomplete — some artifacts are missing or workers reported failure.\n"
            + "\n".join(f"  • {d}" for d in details)
        )
        skip_workers = [f"openenv-{w.replace('_', '-')}" for w in passing]
        return self._construct_prompt(
            base_prompt,
            heading,
            skip_workers,
            target,
            self.__class__._tail(agent_output),
        )

    def _construct_build_feedback(self, base_prompt: str, build_log: str) -> str:
        heading = (
            "The generated Dockerfile or build-context scripts failed authoritative Buildah validation. "
            "Fix `/artifacts/environment/Dockerfile.final`, `/artifacts/environment/setup_runtime.sh`, `/artifacts/environment/repo_setup.sh`, or verifier-related packaging issues as needed. "
            "Keep the build-context contract: the scripts live beside `Dockerfile.final`, `/workspace` must not be copied directly, `repo_setup.sh` is required and immutable, it must materialize `/workspace`, and `setup_runtime.sh` must run after `repo_setup.sh` as a separate build step. The final image must use `WORKDIR /workspace`."
            "The authoritative packaging backend is Buildah, and the build must export `/artifacts/environment/openenv_validation_oci.tar`."
            "After making any packaging, runtime, dependency, or verifier-layout changes, rerun `openenv-build-validator` before considering the build fixed."
        )
        skip = [
            "openenv-repository-explorer",
            "openenv-environment-builder",
            "openenv-eval-builder",
            "openenv-test-analyst",
        ]
        return self._construct_prompt(
            base_prompt,
            heading,
            skip,
            "openenv-dockerfile-builder",
            self.__class__._tail(build_log),
        )

    def _construct_verify_feedback(self, base_prompt: str, verify: VerifyResult) -> str:
        # check the environment phrase issue then trigger the corresponding agent
        target = "openenv-eval-builder"
        fixed_out_lower = (verify.fixed_output or "").lower()
        if any(
            tok in fixed_out_lower
            for tok in ("activat", "source /env", "command not found", "no such file")
        ):
            target = "openenv-environment-builder"

        heading = (
            "External image-level verification failed. "
            "Consume /artifacts/verify_feedback.json and /artifacts/verify_logs/ if those files exist "
            "as the authoritative verification signals and fix any regressions.\n"
            "Note: in the verify_logs you may see eval.sh referenced as /tests/eval.sh rather than "
            "/artifacts/evaluation/eval.sh — this is expected. The outer verifier mounts "
            "/artifacts/evaluation/ as /tests/ inside the container at runtime; both paths point to "
            "the same eval.sh. No path changes are needed.\n"
            "After changing verifier-owned or environment-owned artifacts, rerun `openenv-test-analyst`; "
            "after changing packaging or runtime artifacts, rerun `openenv-build-validator`.\n"
            "Issues found:\n" + "\n".join(f"  • {i}" for i in verify.issues)
        )
        skip = [
            "openenv-repository-explorer",
            "openenv-dockerfile-builder",
        ]
        log_combined = (
            f"[testOnly]\n{verify.base_output}\n\n[testWithFix]\n{verify.fixed_output}"
        )
        return self._construct_prompt(
            base_prompt, heading, skip, target, self.__class__._tail(log_combined)
        )

    async def _post_run_get_trajectory(
        self,
        task_dir: Path | str,
        session_id: str,
        prefix: str,
        run_dir: Path | str = None,
        agent_name: str = None,
    ) -> AgentTrajectory:
        """Get the trajectory by running extraction logic inside the executor"""
        logger.debug(
            "Retrieving agent trajectory by running extraction logic in the executor"
        )

        def _normalise_agent_label(agent: str) -> str:
            """
            Convert an opencode agent type string to a filesystem-safe label.

            Examples:
            "openenv-repository-explorer" → "repository_explorer"
            "openenv-manager"             → "manager"
            "ses_abc12345"                → "ses_abc12345"   (fallback: raw value)
            """
            label = (agent or "").strip()
            if label.startswith("openenv-"):
                label = label[len("openenv-") :]
            return label.replace("-", "_") or "unknown"

        def _extract_trajectory_remote(context):
            """
            This function runs inside the executor to extract trajectory.
            It returns a dictionary matching AgentTrajectory structure.
            """
            import subprocess
            import json
            import os

            task_dir = context.get("task_dir")
            run_dir = context.get("run_dir")
            agent_name = context.get("agent_name")
            agent_version = context.get("agent_version", "unknown")
            latest_session_id = context.get("latest_session_id")
            prefix = context.get("prefix")

            traj_data = None

            try:

                if latest_session_id:
                    output_file = f"{prefix}.traj"
                    output_formated_file = f"{prefix}_formatted.traj"
                    export_cmd = [
                        "opencode",
                        "export",
                        latest_session_id,
                        ">",
                        f"{task_dir}/{output_file}",
                    ]
                    export_cmd = " ".join(export_cmd)
                    proc = subprocess.run(
                        export_cmd,
                        cwd=run_dir,
                        capture_output=True,
                        text=True,
                        shell=True,
                    )
                    if proc.returncode == 0:
                        with open(f"{task_dir}/{output_file}", "r") as f:
                            opencode_json = json.load(f)
                        info = opencode_json.get("info", {})
                        messages = opencode_json.get("messages", [])

                        traj_data = {
                            "metadata": {
                                "session_id": info.get("id"),
                                "project_id": info.get("projectID"),
                            },
                            "steps": [],
                            "agent": {
                                "name": agent_name,
                                "version": info.get("version", agent_version),
                            },
                            "full_metrics": {
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "reasoning_tokens": 0,
                            },
                        }

                        for msg in messages:
                            msg_info = msg.get("info", {})
                            role = msg_info.get("role")
                            step = {
                                "role": role,
                                "step_id": msg_info.get("id", ""),
                                "timestamp": msg_info.get("time", {}).get("created"),
                                "duration": int(
                                    msg_info.get("time", {}).get("completed", 0)
                                )
                                - int(msg_info.get("time", {}).get("created", 0)),
                                "message": [],
                                "reasoning_content": [],
                                "tool_call": [],
                                "model_name": msg_info.get("model", {}).get(
                                    "modelID", ""
                                ),
                                "metrics": {
                                    "input_tokens": msg_info.get("tokens", {}).get(
                                        "input", 0
                                    ),
                                    "output_tokens": msg_info.get("tokens", {}).get(
                                        "output", 0
                                    ),
                                    "reasoning_tokens": msg_info.get("tokens", {}).get(
                                        "reasoning", 0
                                    ),
                                },
                            }
                            traj_data["full_metrics"]["input_tokens"] += step[
                                "metrics"
                            ]["input_tokens"]
                            traj_data["full_metrics"]["output_tokens"] += step[
                                "metrics"
                            ]["output_tokens"]
                            traj_data["full_metrics"]["reasoning_tokens"] += step[
                                "metrics"
                            ]["reasoning_tokens"]

                            for part in msg.get("parts", []):
                                part_type = part.get("type")
                                if part_type == "text":
                                    step["message"].append(part.get("text"))
                                elif part_type == "reasoning":
                                    step["reasoning_content"].append(part.get("text"))
                                elif part_type == "tool":
                                    tool_data = part.get("state", {})
                                    tool_tool = part.get("tool", "")
                                    if tool_tool == "task":
                                        child_context = {
                                            "task_dir": task_dir,
                                            "run_dir": run_dir,
                                            "agent_name": tool_data["input"][
                                                "subagent_type"
                                            ],
                                            "latest_session_id": tool_data["metadata"][
                                                "sessionId"
                                            ],
                                            "agent_version": agent_version,
                                            "prefix": f"{prefix}-{_normalise_agent_label(tool_data['input']['subagent_type'])}",
                                        }
                                        try:
                                            _sub_traj_data = _extract_trajectory_remote(
                                                child_context
                                            )
                                            traj_data["full_metrics"][
                                                "input_tokens"
                                            ] += _sub_traj_data["full_metrics"][
                                                "input_tokens"
                                            ]
                                            traj_data["full_metrics"][
                                                "output_tokens"
                                            ] += _sub_traj_data["full_metrics"][
                                                "output_tokens"
                                            ]
                                            traj_data["full_metrics"][
                                                "reasoning_tokens"
                                            ] += _sub_traj_data["full_metrics"][
                                                "reasoning_tokens"
                                            ]
                                        except Exception as e:
                                            pass
                                    step["tool_call"].append(
                                        {
                                            "name": part.get("tool", ""),
                                            "tool_id": part.get("callID", ""),
                                            "arguments": tool_data.get("input"),
                                            "title": tool_data.get("title"),
                                            "result": (
                                                tool_data.get("output")
                                                if tool_data.get("status")
                                                == "completed"
                                                else tool_data.get("error")
                                            ),
                                            "status": tool_data.get("status"),
                                            "duration": tool_data.get("time", {}).get(
                                                "start", 0
                                            )
                                            - tool_data.get("time", {}).get("end", 0),
                                        }
                                    )
                            step["message"] = "\n".join(step["message"])
                            step["reasoning_content"] = "\n".join(
                                step["reasoning_content"]
                            )
                            traj_data["steps"].append(step)

                        # Save formatted trajectory inside the task dir as well
                        with open(f"{task_dir}/{output_formated_file}", "w") as f:
                            json.dump(traj_data, f)

                        return traj_data

            except Exception as e:
                raise Exception(
                    f"Error to parse the trajectory because of the error:{e}"
                )

        # Prepare payload for remote execution just like orchestrator, copied here
        payload = {
            "func": _extract_trajectory_remote,
            "instruction": {
                "task_dir": str(task_dir),
                "run_dir": str(run_dir) if run_dir else None,
                "agent_name": agent_name,
                "agent_version": "unknown",
                "latest_session_id": session_id,
                "prefix": f"{prefix}-{_normalise_agent_label(agent_name)}",
            },
        }

        # Create temporary files for transfer
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f_in:
            cloudpickle.dump(payload, f_in)
            input_local = f_in.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f_script:
            f_script.write(_UDF_WRAPPER)
            script_local = f_script.name

        remote_input = f"{task_dir}/traj_input.pkl"
        remote_output = f"{task_dir}/traj_output.pkl"
        remote_script = f"{task_dir}/traj_udf.py"
        output_local = None

        try:
            # Upload files
            await self._sandbox.put_file(input_local, remote_input)
            await self._sandbox.put_file(script_local, remote_script)

            # Execute remote script
            exec_cmd = [
                _ENV_ENABLE_CMD,
                "&&",
                "python",
                remote_script,
                remote_input,
                remote_output,
            ]
            res = await self._sandbox.exec(exec_cmd)

            if res.return_code != 0:
                logger.error(f"Remote trajectory extraction failed: {res.stderr}")
                raise EnvironmentError(f"Remote extraction failed: {res.stderr}")
            with tempfile.NamedTemporaryFile(mode="wb", delete=False) as f_out:
                output_local = f_out.name

            await self._sandbox.get_file(remote_output, output_local, binary=True)
            await self._sandbox.exec(["rm", remote_input, remote_output, remote_script])
            with open(output_local, "rb") as f:
                result = cloudpickle.load(f)

            if result["status"] == 0:
                traj_data = result["result"]
                if traj_data:
                    return AgentTrajectory(**traj_data)
                else:
                    raise EnvironmentError("Remote extraction returned empty result")
            else:
                raise EnvironmentError(f"Remote extraction error: {result['result']}")

        except Exception as e:
            logger.error(f"Failed to get agent trajectory: {e}", exc_info=True)
            raise

        finally:
            # Cleanup local files
            if os.path.exists(input_local):
                os.unlink(input_local)
            if os.path.exists(script_local):
                os.unlink(script_local)

    async def _snapshot_sessions(self, run_dir: Optional[str]) -> set[str]:
        """Return the set of current opencode session IDs."""
        result = await self._sandbox.exec(
            ["opencode session list --format json 2>/dev/null || echo '[]'"],
            cwd=run_dir,
        )
        try:
            sessions = json.loads(result.stdout.strip() or "[]")
            if isinstance(sessions, list):
                return {s["id"] for s in sessions if isinstance(s, dict) and "id" in s}
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
        return set()

    async def _collect_turn_trajectories(
        self,
        turn: int,
        task_dir: str,
        pre_session_ids: set[str],
        run_dir: Optional[str],
        agent_name: str = None,
    ) -> Optional[AgentTrajectory]:
        """
        Export all opencode sessions created during this turn and save them with
        a prefix chain that reflects the parent→child invocation hierarchy.
        """
        post_session_ids = await self._snapshot_sessions(run_dir)
        new_ids = post_session_ids - pre_session_ids
        if not new_ids:
            logger.debug(f"[{self.name}] turn {turn}: no new sessions.")
            return None
        traj = None
        result = await self._sandbox.exec(["mkdir", "-p", f"{task_dir}/trajectories"])
        if result.return_code != 0:
            logger.warning("Not able to create the trajectories folder")
        for sid in new_ids:
            try:
                traj = await self._post_run_get_trajectory(
                    task_dir=f"{task_dir}/trajectories",
                    prefix=f"opencode-turn-{turn:02d}",
                    session_id=sid,
                    run_dir=run_dir,
                    agent_name=agent_name,
                )

            except Exception as e:
                logger.warning(f"Failed to get agent trajectory: {e}")
        return traj
