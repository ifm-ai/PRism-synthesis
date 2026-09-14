from agentdist.agents.protocol import Agent
from agentdist.executors import ExecutionBackend
from agentdist.llm import fake_tool_capture_server as _capture_server_module
from agentdist.structures.agent import (
    AgentContext,
    AgentCoreConfig,
    AgentResult,
    AgentTrajectory,
    AgentTrajectoryTool,
)
from agentdist.observability.logging import Logger
from pathlib import Path
import json
from agentdist.exceptions import AgentSetupError
import shlex
import tempfile
import cloudpickle
import os
from agentdist.constants import _UDF_WRAPPER, _ENV_ENABLE_CMD

logger = Logger.get_logger(__name__)


class OpenCodeAgent(Agent):
    """This is a open code wrapper to be used to run in the environment to be executed"""

    name = "OpenCode"
    docs = "https://opencode.ai/docs"
    _VERSION = "v1.4.6"
    _SETUP_CMD = ["npm install -g opencode-ai"]
    _DY_SETUP_CMD = ["curl", "-fsSL", "https://raw.githubusercontent.com/anomalyco/opencode/refs/heads/dev/install", "|", "VERSION=v1.4.6","bash","&&", "ln", "-sf", "$HOME/.opencode/bin/opencode", "/usr/local/bin/opencode"]

    def __init__(self, exec: ExecutionBackend, agent_config: AgentCoreConfig) -> None:
        """Initialization class for the agent"""
        self._config = agent_config
        self._sandbox = exec
        self.name = self._config.name
        self.agent_path = agent_config.get("agent_path", "/.opencode")

        run_config = agent_config.agent_run_config or {}
        self._capture_tool_schema = bool(run_config.get("capture_tool_schema", False))
        self._capture_tool_schema_port = run_config.get("capture_tool_schema_port", 8813)

    async def _detect_distro(self) -> str:
        """Returns the lowercase distro ID from /etc/os-release (e.g. 'ubuntu', 'alpine').
        Falls back to 'unknown' if the file cannot be read or parsed."""
        result = await self._sandbox.exec(["cat", "/etc/os-release"])
        if result.return_code != 0:
            return "unknown"
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("ID="):
                return line.split("=", 1)[1].strip().strip('"').lower()
        return "unknown"

    async def _install_dependencies(self):
        """Install curl and ripgrep using the package manager appropriate for the detected Linux distro."""
        distro = await self._detect_distro()
        logger.debug(f"Detected Linux distro: '{distro}'")

        if distro in ("ubuntu", "debian", "linuxmint", "pop", "elementary", "kali", "raspbian"):
            cmd = ["apt-get", "update", "&&", "apt-get", "install", "-y", "--no-install-recommends", "curl", "ripgrep"]
            env = {"DEBIAN_FRONTEND": "noninteractive"}
        elif distro == "fedora":
            cmd = ["dnf", "install", "-y", "curl", "ripgrep"]
            env = {}
        elif distro in ("rhel", "centos", "rocky", "almalinux", "ol"):
            # RHEL/CentOS 8+ ship dnf; older versions only have yum
            has_dnf = await self._sandbox.exec(["which", "dnf"])
            cmd = ["dnf", "install", "-y", "curl", "ripgrep"] if has_dnf.return_code == 0 \
                else ["yum", "install", "-y", "curl", "ripgrep"]
            env = {}
        elif distro == "alpine":
            cmd = ["apk", "add", "--no-cache", "curl", "ripgrep"]
            env = {}
        elif distro in ("opensuse-leap", "opensuse-tumbleweed", "sles"):
            cmd = ["zypper", "--non-interactive", "install", "curl", "ripgrep"]
            env = {}
        elif distro == "arch":
            cmd = ["pacman", "-Sy", "--noconfirm", "curl", "ripgrep"]
            env = {}
        else:
            # Unknown distro — probe for a package manager in preference order
            logger.warning(f"Unknown distro '{distro}', probing for a package manager.")
            for binary, install_cmd, install_env in [
                ("apt-get", ["apt-get", "update", "&&", "apt-get", "install", "-y", "--no-install-recommends", "curl", "ripgrep"], {"DEBIAN_FRONTEND": "noninteractive"}),
                ("dnf",     ["dnf",    "install", "-y",              "curl", "ripgrep"], {}),
                ("yum",     ["yum",    "install", "-y",              "curl", "ripgrep"], {}),
                ("apk",     ["apk",    "add", "--no-cache",          "curl", "ripgrep"], {}),
                ("zypper",  ["zypper", "--non-interactive", "install","curl", "ripgrep"], {}),
                ("pacman",  ["pacman", "-Sy", "--noconfirm",         "curl", "ripgrep"], {}),
            ]:
                if (await self._sandbox.exec(["which", binary])).return_code == 0:
                    return await self._sandbox.exec(install_cmd, env=install_env or None)
            raise AgentSetupError(
                f"Distro '{distro}' is not recognised and no supported package manager "
                "was found. Please pre-install curl and ripgrep."
            )

        return await self._sandbox.exec(cmd, env=env or None)

    async def setup(self):
        """The setup of opencode in the environment"""
        
        logger.debug(
            f"Setting up {self.name} agent in {self._sandbox.__class__.__name__}"
        )

        result = await self._sandbox.exec(["mkdir", "-p", self.agent_path])
        if result.return_code != 0:

            raise AgentSetupError(
                f"Failed to create agent path '{self.agent_path}'. Stderr: {result.stderr}"
            )
        
        if self._config.skip_setup:
            logger.debug(
                f"{self.name} agent setup skipped because of the configuration."
            )
            if self._capture_tool_schema:
                await self._run_tool_schema_capture()
            return

        # check the npm installation and version
        result = await self._sandbox.exec(["npm", "--version"])
        if result.return_code != 0:
            result = await self._install_dependencies()
            if result.return_code != 0:
                raise AgentSetupError(
                    f"curl/ripgrep installation failed. Stderr: {result.stderr}"
                )
            result = await self._sandbox.exec(self.__class__._DY_SETUP_CMD)
            if result.return_code != 0:
                raise AgentSetupError(
                    f"Agent setup through dynamic installation failed. Stderr: {result.stderr}"
                )
        else:
            result = await self._sandbox.exec(
                self.__class__._SETUP_CMD, cwd=self.agent_path
            )
            if result.return_code != 0:
                raise AgentSetupError(
                    f"Setup for {self.name} agent failed. Stderr: {result.stderr}"
                )
        logger.debug(f"{self.name} agent setup complete.")

        if self._capture_tool_schema:
            await self._run_tool_schema_capture()

    async def _run_tool_schema_capture(self) -> None:
        """Just a helper function to run the tool schema capture in the executor"""
        port = self._capture_tool_schema_port
        remote_server = f"{self.agent_path}/capture_server.py"
        remote_output = f"{self.agent_path}/agent_tools.json"
        opencode_cfg = {
            "$schema": "https://opencode.ai/config.json",
            "permission": {"bash": "allow", "edit": "allow", "read": "allow",
    "grep": "allow",
    "glob": "allow",
    "list": "allow",
    "websearch": "allow",
    "webfetch": "allow"},
            "provider": {
                "vllm": {
                    "npm": "@ai-sdk/openai-compatible",
                    "options": {"baseURL": f"http://127.0.0.1:{port}/v1"},
                    "models": {"test": {"name": "test"}},
                }
            },
            "model": "vllm/test",
        }
        try:
            await self._sandbox.put_file(_capture_server_module.__file__, remote_server)
            script = "\n".join(
                [
                    "set -e",
                    f"python3 {shlex.quote(remote_server)} --output {shlex.quote(remote_output)} --port {port} > /dev/null 2>&1 &",
                    "SERVER_PID=$!",
                    f"for i in $(seq 1 50); do (echo > /dev/tcp/127.0.0.1/{port}) 2>/dev/null && break; sleep 0.1; done",
                    f'OPENCODE_CONFIG_CONTENT={shlex.quote(json.dumps(opencode_cfg))} opencode --model vllm/test --print-logs run --format=json -- "what model is this?" < /dev/null || true',
                    "kill -9 $SERVER_PID 2>/dev/null || true",
                ]
            )
            result = await self._sandbox.exec(["bash", "-c", script], timeout=120)
            if result.return_code != 0:
                logger.warning(f"Tool schema capture exited non-zero: {result.stderr}")
        except Exception as e:
            logger.warning(f"Failed to capture tool schema: {e}")

    async def _post_run_get_trajectory(
        self, task_dir: Path | str, run_dir: Path | str = None
    ) -> AgentTrajectory:
        """Get the trajectory by running extraction logic inside the executor"""
        logger.debug(
            "Retrieving agent trajectory by running extraction logic in the executor"
        )
        self._last_opencode_finish_ok = False

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
            file_name = context.get("file_name")


            traj_data = None

            try:
                if not latest_session_id:
                    list_cmd = [
                        "opencode",
                        "session",
                        "list",
                        "--max-count",
                        "1",
                        "--format",
                        "json",
                    ]
                    proc = subprocess.run(
                        list_cmd, cwd=run_dir, capture_output=True, text=True
                    )
                    if proc.returncode == 0 and proc.stdout.strip():
                        try:
                            latest_session_id = json.loads(proc.stdout.strip())[0]["id"]
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass

                if latest_session_id:
                    export_cmd = [
                        "opencode",
                        "export",
                        latest_session_id,
                        ">",
                        f"{task_dir}/{file_name}.traj",
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
                        with open(f"{task_dir}/{file_name}.traj", "r") as f:
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
                                            "file_name": f"opencode-subagent-{tool_id}.traj",
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
                                                "end", 0
                                            )
                                            - tool_data.get("time", {}).get("start", 0),
                                        }
                                    )
                            step["message"] = "\n".join(step["message"])
                            step["reasoning_content"] = "\n".join(
                                step["reasoning_content"]
                            )
                            traj_data["steps"].append(step)

                        # Save formatted trajectory inside the task dir as well
                        with open(f"{task_dir}/{file_name}_formatted.traj", "w") as f:
                            json.dump(traj_data, f)

                        return traj_data
            except Exception as e:
                pass

            # Fallback to opencode.out parsing
            try:
                out_file = f"{task_dir}/opencode.out"
                if not os.path.exists(out_file):
                    return None

                traj_data = {
                    "metadata": {"session_id": "unknown", "project_id": "unknown"},
                    "steps": [],
                    "agent": {"name": agent_name, "version": agent_version},
                    "full_metrics": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                    },
                }

                events_by_msg_id = {}
                events_order = []

                with open(out_file, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            event = json.loads(line)
                            part = event.get("part", {})
                            msg_id = part.get("messageID")
                            if not msg_id:
                                continue
                            if msg_id not in events_by_msg_id:
                                events_by_msg_id[msg_id] = []
                                events_order.append(msg_id)
                            events_by_msg_id[msg_id].append(event)
                            if traj_data["metadata"]["session_id"] == "unknown":
                                traj_data["metadata"]["session_id"] = event.get(
                                    "sessionID", "unknown"
                                )
                        except json.JSONDecodeError:
                            continue

                for msg_id in events_order:
                    events = events_by_msg_id[msg_id]
                    metrics = {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_tokens": 0,
                    }
                    timestamp = 0
                    role = "assistant"

                    step = {
                        "role": role,
                        "step_id": None,
                        "timestamp": timestamp,
                        "duration": 0,
                        "message": [],
                        "reasoning_content": [],
                        "tool_call": [],
                        "model_name": "",
                        "metrics": metrics,
                    }
                    for e in events:
                        part = e.get("part", {})
                        if step["step_id"] is None:
                            step["step_id"] = part.get("id")
                        ptype = part.get("type")
                        if ptype == "step-start":
                            timestamp = e.get("timestamp", 0)
                        elif ptype == "text":
                            step["message"].append(part.get("text", ""))
                        elif ptype == "reasoning":
                            step["reasoning_content"].append(part.get("text", ""))
                        elif ptype == "tool":
                            tool_data = part.get("state", {})
                            step["tool_call"].append(
                                {
                                    "name": part.get("tool", ""),
                                    "tool_id": part.get("callID", ""),
                                    "arguments": tool_data.get("input"),
                                    "title": tool_data.get("title"),
                                    "result": (
                                        tool_data.get("output")
                                        if tool_data.get("status") == "completed"
                                        else tool_data.get("error")
                                    ),
                                    "status": tool_data.get("status"),
                                    "duration": 0,
                                }
                            )
                            step["result"] = tool_data.get("output")
                        elif ptype == "step-finish":
                            step["metrics"]["input_tokens"] = part.get(
                                "tokens", {}
                            ).get("input", 0)
                            step["metrics"]["output_tokens"] = part.get("tokens", {}).get("output", 0)
                            
                            step["metrics"]["reasoning_tokens"] = part.get(
                                "tokens", {}
                            ).get("reasoning", 0)
                            traj_data["full_metrics"]["input_tokens"] += part.get(
                                "tokens", {}
                            ).get("input", 0)
                            traj_data["full_metrics"]["output_tokens"] += part.get(
                                "tokens", {}
                            ).get("output", 0)
                            traj_data["full_metrics"]["reasoning_tokens"] += part.get(
                                "tokens", {}
                            ).get("reasoning", 0)
                    step["message"] = "\n".join(step["message"])
                    step["reasoning_content"] = "\n".join(step["reasoning_content"])
                    traj_data["steps"].append(step)

                final_ok = False
                if events_order:
                    last_events = events_by_msg_id[events_order[-1]]
                    final_ok = any(
                        e.get("part", {}).get("type") == "step-finish"
                        and e.get("part", {}).get("reason") == "stop"
                        for e in last_events
                    )
                traj_data["_final_step_ok"] = final_ok

                with open(f"{task_dir}/{file_name}_formatted.traj", "w") as f:
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
                "agent_name": self.name,
                "agent_version": "unknown",
                "latest_session_id": None,
                "file_name": "opencode"
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
                    self._last_opencode_finish_ok = bool(
                        traj_data.pop("_final_step_ok", False)
                    )
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

    async def _capture_agent_info(self):
        """"Capture the agent info for the run"""
        info = {"name": "opencode", "version": self.__class__._VERSION, "agent_run_config": self._config.agent_run_config, "agent_config": {}}
        result = await self._sandbox.exec(["echo","$OPENCODE_CONFIG_CONTENT"])
        if result.return_code != 0:
            logger.warning(f"Failed to retrieve OPENCODE_CONFIG_CONTENT: {result.stderr}")
            return json.dumps(info)
        try:
            agent_config = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse OPENCODE_CONFIG_CONTENT as JSON: {e}")
            agent_config = {}
        info["agent_config"] = agent_config
        return json.dumps(info)

    
    async def run(self, instruction: str, agent_context: AgentContext) -> AgentResult:
        """The agent command run on the instruction and return the result"""
        logger.debug(f"Running {self.name} agent with instruction: '{instruction}'")

        ### capture the agent info for the run
        agent_info = await self._capture_agent_info()
        agent_info_path = f"{agent_context.task_dir}/agent_info.json"
        try:
            await self._sandbox.exec(
                ["echo", shlex.quote(str(agent_info)), ">", agent_info_path]
            )
        except Exception as e:
            logger.warning(f"Not able to save the agent info in task folder due to error: {e}")

        result = await self._sandbox.exec(
            [
                "echo",
                shlex.quote(instruction),
                ">",
                f"{agent_context.task_dir}/instruction.md",
            ]
        )
        if result.return_code != 0:
            logger.warning(
                f"Not able to save the instruction in task folder due to error: {result.stderr}"
            )

        if self._capture_tool_schema:
            try:
                await self._sandbox.exec(
                    [f"cp {self.agent_path}/agent_tools.json {agent_context.task_dir}/agent_tools.json"]
                )
            except Exception as e:
                logger.debug(f"No captured tool schema to retrieve: {e}")

        cmd = ["opencode"]
        if self._config.model:
            cmd += ["--model", self._config.model]
        cmd += [
            "--print-logs",
            "run",
            "--thinking",
            "--format=json",
            "--",
            f'"$(cat {agent_context.task_dir}/instruction.md)"',
            ">",
            f">(tee {agent_context.task_dir}/opencode.out)",
            "2>",
            f">(tee {agent_context.task_dir}/opencode.log)" "< /dev/null",
        ]

        result = await self._sandbox.exec(
            cmd,
            env=agent_context.env_vars,
            cwd=agent_context.run_dir,
            timeout=self._config.run_timeout,
        )

        try:
            trajectory = await self._post_run_get_trajectory(
                task_dir=agent_context.task_dir, run_dir=agent_context.run_dir
            )
        except Exception as e:
            logger.warning(f"Failed to get agent trajectory: {e}")
            trajectory = None

        result = AgentResult(
            status=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            trajectory=trajectory,
        )
        finished_cleanly = getattr(self, "_last_opencode_finish_ok", False)
        result.status = 0 if (result.status == 0 and finished_cleanly) else -1
        return result
