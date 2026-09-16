import json
import os
from pathlib import Path
import shlex
import tempfile
import cloudpickle
from agentdist.constants import _ENV_ENABLE_CMD, _UDF_WRAPPER
from typing import Optional

from agentdist.agents.opencode import OpenCodeAgent
from agentdist.executors.protocol import ExecutionBackend
from agentdist.observability.logging import Logger
from agentdist.structures.agent import AgentContext, AgentCoreConfig, AgentResult, AgentTrajectory
from synthesis import CONTINUATION_NUDGE, RawPr, SynthesizedTask, compact_handoff, synthesize_task
from trajectory import ChainSegment, combine_segments

logger = Logger.get_logger(__name__)


def _last_assistant_message(trajectory: AgentTrajectory) -> str:
    for step in reversed(trajectory.steps):
        if step.role == "assistant" and step.message:
            return step.message
    return ""





class PRChainCustomAgent(OpenCodeAgent):
    name = "PRChainCustomAgent"

    def __init__(self, exec: ExecutionBackend, agent_config: AgentCoreConfig) -> None:
        super().__init__(exec, agent_config)
        run_config = agent_config.agent_run_config
        self.chain_record = run_config["chain_record_path"]
        self.chain_length = run_config["chain_length"]
        self.synthesis_base_url = run_config["synthesis_base_url"]
        self.synthesis_model = run_config["synthesis_model"]
        self.synthesis_api_key = run_config.get("synthesis_api_key")
        self.synthesis_extra_args = run_config.get("synthesis_extra_args", {})
        self.synthesis_max_tokens = run_config.get("synthesis_max_tokens", 32000)
        self.max_resume_attempts = run_config.get("max_resume_attempts", 3)
        self.token_budget = run_config.get("token_budget", 512_000)

    def _get_turn(
    self,chain_record: dict, index: int, base_url: str, api_key: str | None, model: str, max_tokens: int = 32000, extra_args: dict = {}
) -> tuple[RawPr, SynthesizedTask]:
        extra = chain_record.get("extra", {})
        if index == 0:
            raw_pr = RawPr(
                repo_full_name=extra["repo"],
                pr_number=extra["pr_numbers"][0],
                base_commit=extra.get("base_commit", ""),
                title=chain_record.get("extra", {}).get("title", ""),
                body="",
                diff="",
            )
            instruction = chain_record["instruction"]
            task = SynthesizedTask(
                title=raw_pr.title, description=instruction, acceptance_criteria=[], instruction=instruction
            )
            return raw_pr, task

        entry = extra["pr_chain"][index - 1]
        raw_pr = RawPr(
            repo_full_name=extra["repo"],
            pr_number=entry["pr_number"],
            base_commit=entry.get("base_commit", extra.get("base_commit", "")),
            title=entry.get("title", ""),
            body=entry.get("body", ""),
            diff=entry.get("diff", ""),
            base_files=entry.get("base_files", []),
            comments=entry.get("comments", []),
            touched_files=entry.get("touched_files", []),
        )
        description = entry.get("description")
        if description:
            task = SynthesizedTask(
                title=raw_pr.title, description=description, acceptance_criteria=[], instruction=description
            )
        else:
            task = synthesize_task(raw_pr, base_url=base_url, api_key=api_key, model=model,max_tokens=max_tokens, extra_args=extra_args)
        return raw_pr, task

    async def _run_opencode_turn(
        self, prompt: str, turn: int, context: AgentContext
    ) -> tuple[str, int]:
        await self._sandbox.exec([f"mkdir -p {context.task_dir}/prompts {context.task_dir}/logs"])
        prompt_path = f"{context.task_dir}/prompts/turn-{turn:02d}.md"
        out_path = f"{context.task_dir}/logs/turn-{turn:02d}.out"
        log_path = f"{context.task_dir}/logs/turn-{turn:02d}.log"
        await self._sandbox.exec(
            [f"printf '%s' {shlex.quote(prompt)} > {shlex.quote(prompt_path)}"]
        )
        model_flag = f"--model {shlex.quote(self._config.model)} " if self._config.model else ""
        run_cmd = [
            f"opencode {model_flag}--print-logs run --thinking --format=json -- "
            f'"$(cat {shlex.quote(prompt_path)})" '
            f"> >(tee {shlex.quote(out_path)}) 2> >(tee {shlex.quote(log_path)}) < /dev/null"
        ]
        result = await self._sandbox.exec(
            run_cmd, env=context.env_vars, cwd=context.run_dir, timeout=self._config.run_timeout
        )
        out_result = await self._sandbox.exec(["cat", out_path])
        output = out_result.stdout if out_result.return_code == 0 else (result.stdout or "")
        return output, result.return_code

    async def _discover_new_session(self, pre_session_ids: set[str], run_dir: str | None) -> str | None:
        new_ids = (await self._snapshot_sessions(run_dir)) - pre_session_ids
        if not new_ids:
            return None
        return sorted(new_ids)[0]

    async def _run_opencode_continue(
        self, session_id: str, turn: int, attempt: int, context: AgentContext
    ) -> tuple[str, int]:
        """Resume session used for interrupted sessions
        """

        await self._sandbox.exec([f"mkdir -p {context.task_dir}/logs"])
        out_path = f"{context.task_dir}/logs/turn-{turn:02d}-resume-{attempt:02d}.out"
        log_path = f"{context.task_dir}/logs/turn-{turn:02d}-resume-{attempt:02d}.log"
        model_flag = f"--model {shlex.quote(self._config.model)} " if self._config.model else ""
        run_cmd = [
            f"opencode {model_flag}--print-logs run --session {shlex.quote(session_id)} "
            f"--thinking --format=json -- {shlex.quote(CONTINUATION_NUDGE)} "
            f"> >(tee {shlex.quote(out_path)}) 2> >(tee {shlex.quote(log_path)}) < /dev/null"
        ]
        result = await self._sandbox.exec(
            run_cmd, env=context.env_vars, cwd=context.run_dir, timeout=self._config.run_timeout
        )
        out_result = await self._sandbox.exec(["cat", out_path])
        output = out_result.stdout if out_result.return_code == 0 else (result.stdout or "")
        return output, result.return_code

    async def _save_combined(
        self, context: AgentContext, index: int, segments: list[ChainSegment]
    ) -> None:
        """Save the trajectories combined
        """
        local_path = None
        try:
            combined_json = json.dumps(combine_segments(segments))
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                f.write(combined_json)
                local_path = f.name

            await self._sandbox.put_file(local_path, f"{context.task_dir}/pr_chain_conversation.json")

        finally:
            if local_path is not None:
                os.unlink(local_path)
    
    @staticmethod
    def _turn_token_delta(trajectory: AgentTrajectory) -> int:
        """Estimate this turn's net contribution to token usage."""
        steps = trajectory.steps
        if not steps:
            return 0
        assistant_steps = [s for s in steps if s.role == "assistant"]
        if not assistant_steps:
            return 0
        baseline = steps[0].metrics.input_tokens
        last = assistant_steps[-1]
        delta = (last.metrics.input_tokens - baseline) + last.metrics.output_tokens + last.metrics.reasoning_tokens
        return max(delta, 0)
    async def run(self, instruction: str, context: AgentContext) -> AgentResult:
        """This method run the chain of pr's where it runs until the one pr task completed."""
        del instruction
        segments: list[ChainSegment] = []
        incomplete_turns: list[int] = []
        last_exit_code = -1
        cumulative_tokens = 0
        budget_exhausted = False
        logger.info("Starting the Multi-User Agent Chain Agent")
        index = 0
        try:
            with open(self.chain_record, "r") as f:
                chain_record = json.load(f)
        except Exception as e:
            logger.error(f"Error while parsing the chain record from path :{self.chain_record}: {e}")
            return AgentResult(
            status=-1,
            stdout="",
            stderr=str(e),
            trajectory=None,
        )

        await self._sandbox.put_file(self.chain_record, f"{context.task_dir}/chain_record.json")

        try:
            while index < self.chain_length:
                if self.token_budget is not None and cumulative_tokens >= self.token_budget:
                    budget_exhausted = True
                    logger.info(
                        f"cumulative trajectory tokens {cumulative_tokens} reached token "
                        f"budget {self.token_budget} after turn {index - 1}; stopping chain "
                        f"at {index}/{self.chain_length} turns"
                    )
                    break

                raw_pr, task = self._get_turn(
                    chain_record,
                    index,
                    base_url=self.synthesis_base_url,
                    api_key=self.synthesis_api_key,
                    model=self.synthesis_model,
                )
                handoff = None
                if index > 0:
                    handoff = compact_handoff(
                        base_url=self.synthesis_base_url,
                        api_key=self.synthesis_api_key,
                        model=self.synthesis_model,
                        max_tokens = self.synthesis_max_tokens,
                        extra_args = self.synthesis_extra_args,
                        prior_summary=segments[-1].handoff,
                        prior_pr=segments[-1].raw_pr,
                        prior_task=segments[-1].task,
                        solver_final_message=_last_assistant_message(segments[-1].trajectory),
                        next_task=task,
                    )
                prompt = f"{handoff}\n\n{task.instruction}" if handoff else task.instruction

                logger.info(f"turn {index} (PR #{raw_pr.pr_number}): starting")
                pre_session_ids = await self._snapshot_sessions(context.run_dir)
                _, last_exit_code = await self._run_opencode_turn(prompt, index, context)
                session_id = await self._discover_new_session(pre_session_ids, context.run_dir)
                if session_id is None:
                    logger.info(f"turn {index} (PR #{raw_pr.pr_number}): no new opencode session produced, stopping chain")
                    break
                try:
                    exported = await self._post_run_get_trajectory(context.task_dir,session_id,f"opencode-turn-{index}" ,context.run_dir)
                except Exception as e:
                    logger.warning(f"Failure to export the trajectory for the turn with error {e}, skipping")
                    exported = None
                trajectory, is_clean = exported if exported else (None, False)
                logger.info(
                    f"turn {index} (PR #{raw_pr.pr_number}) session {session_id}: initial finish="
                    f"{'stop' if is_clean else ('export-failed' if exported is None else 'incomplete')}"
                )

                attempt = 0
                while not is_clean and attempt < self.max_resume_attempts:
                    attempt += 1
                    logger.info(f"turn {index} session {session_id}: resume attempt {attempt}/{self.max_resume_attempts}")
                    await self._run_opencode_continue(session_id, index, attempt, context)
                    try:
                        exported = await self._post_run_get_trajectory(context.task_dir,session_id,f"opencode-turn-{index}-ampt-{attempt}" ,context.run_dir)
                    except Exception as e:
                        logger.warning(f"Failure to export the trajectory for the turn with error {e}, skipping")
                        exported = None
                    if exported is not None:
                        trajectory, is_clean = exported
                    logger.info(
                        f"turn {index} session {session_id}: resume attempt {attempt} finish="
                        f"{'stop' if is_clean else ('export-failed' if exported is None else 'incomplete')}"
                    )

                if trajectory is None:
                    logger.info(f"turn {index} session {session_id}: never produced an exportable trajectory, stopping chain")
                    break
                if is_clean:
                    logger.info(f"turn {index} session {session_id}: finished cleanly")
                else:
                    incomplete_turns.append(index)
                    logger.info(
                        f"turn {index} session {session_id}: exhausted {self.max_resume_attempts} resume "
                        "attempts, keeping partial trajectory and continuing to next PR"
                    )

                segments.append(ChainSegment(raw_pr=raw_pr, task=task, handoff=handoff, trajectory=trajectory))
                turn_tokens = self.__class__._turn_token_delta(trajectory)
                cumulative_tokens += turn_tokens # just ignoring the 
                logger.info(
                    f"turn {index}: {turn_tokens} tokens this turn, "
                    f"{cumulative_tokens}/{self.token_budget} cumulative"
                )
                await self._save_combined(context, index, segments)
                index += 1
        except Exception as e:
            final_status = {
            "total_solved":len(segments),
            "total_turns":self.chain_length,
            "incomplete_turns":incomplete_turns,
            "cumulative_tokens":cumulative_tokens,
            "token_budget":self.token_budget,
            "budget_exhausted":budget_exhausted,
            "error": str(e)
        }
            await self._sandbox.exec([f"printf '%s' {shlex.quote(json.dumps(final_status))} > {context.task_dir}/final_stats.json"])
            return AgentResult(status=-1, stdout="", stderr=f"Error: {e}", trajectory=None)

        if not segments:
            final_status = {
            "total_solved":len(segments),
            "total_turns":self.chain_length,
            "incomplete_turns":incomplete_turns,
            "cumulative_tokens":cumulative_tokens,
            "token_budget":self.token_budget,
            "budget_exhausted":budget_exhausted,
            "error": "no chain turn produced a trajectory"
        }
            await self._sandbox.exec([f"printf '%s' {shlex.quote(json.dumps(final_status))} > {context.task_dir}/final_stats.json"])
            return AgentResult(status=-1, stdout="", stderr="no chain turn produced a trajectory", trajectory=None)

        solved, total = len(segments), self.chain_length
        ran_to_completion = solved == total or budget_exhausted
        status = 0 if ran_to_completion and not incomplete_turns else (last_exit_code or 1)
        final_status = {
            "total_solved":solved,
            "total_turns":total,
            "incomplete_turns":incomplete_turns,
            "cumulative_tokens":cumulative_tokens,
            "token_budget":self.token_budget,
            "budget_exhausted":budget_exhausted,
        }
        await self._sandbox.exec([f"printf '%s' {shlex.quote(json.dumps(final_status))} > {context.task_dir}/final_stats.json"])
        stdout = f"solved {solved}/{total} chain turns ({len(incomplete_turns)} incomplete: {incomplete_turns})"
        if budget_exhausted:
            stdout += f"; stopped early at {cumulative_tokens} cumulative tokens (budget {self.token_budget})"
        return AgentResult(
            status=status,
            stdout=stdout,
            stderr="",
            trajectory=segments[-1].trajectory,
        )


    async def _post_run_get_trajectory(
        self,
        task_dir: Path | str,
        session_id: str,
        prefix: str,
        run_dir: Path | str = None,
    ) -> tuple[AgentTrajectory, bool] | None:
        """Get the trajectory by running extraction logic inside the executor"""
        logger.debug(
            "Retrieving agent trajectory by running extraction logic in the executor"
        )

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
                                "name": "multturnagent",
                                "version": info.get("version", agent_version),
                            },
                            "full_metrics": {
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "reasoning_tokens": 0,
                            },
                            "_final_step_ok": bool(messages)
                            and messages[-1].get("info", {}).get("role") == "assistant"
                            and messages[-1].get("info", {}).get("finish") == "stop",
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
                                    tool_id = part.get("callID", "")
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
                                            "prefix": f"{prefix}-{tool_id}",
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
                "agent_version": "unknown",
                "latest_session_id": session_id,
                "prefix": f"{prefix}",
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
                    is_finish = bool(traj_data.pop("_final_step_ok", False))
                    return AgentTrajectory(**traj_data), is_finish
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