from agentdist.executors.protocol import ExecutionBackend
from agentdist.structures.executor import ContainerExecConfig, EnvironmentExecResult
from agentdist.exceptions import EnvironmentError
from agentdist.constants import _DEFAULT_ENV_FILE_MODE
import asyncio
from agentdist.observability.logging import Logger
from pathlib import Path
from typing import List
from uuid import uuid4
import shlex
from typing import Any, Dict

logger = Logger.get_logger(__name__)


class DockerExecutionBackend(ExecutionBackend):
    """This class acts as contract is used to run the agent in the docker executor as local"""

    def __init__(self, env_config: ContainerExecConfig):
        """This is used to specify the environment configuration"""
        self._env_config = env_config
        self.env_id = uuid4().hex
        self.container_id = None
        self._executable = "docker"

    @property
    def env_name(self):
        return f"docker_{self.env_id}"

    async def _run_cmd(self, cmd: list, timeout: int = None,decode_bytes = True) -> EnvironmentExecResult:
        process = None
        try:
            logger.debug(f"Running command: {' '.join(cmd)}")
            process = await asyncio.create_subprocess_shell(
                " ".join(cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            if decode_bytes:
                stdout = stdout_bytes.decode().strip()
                stderr = stderr_bytes.decode().strip()
            else:
                stdout = stdout_bytes
                stderr = stderr_bytes

            logger.debug(f"Command finished with return code {process.returncode}")
            if process.returncode != 0:
                logger.warning(f"Command stderr: {stderr}")

            return EnvironmentExecResult(
                return_code=process.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        except asyncio.TimeoutError:
            logger.error(f"Command timed out after {timeout} seconds.")
            if process:
                try:
                    process.kill()
                    await process.wait()
                except ProcessLookupError:
                    pass  # Process already terminated
            return EnvironmentExecResult(return_code=-1, stdout="", stderr="Timeout")
        except FileNotFoundError:
            logger.error(f"Command not found: {cmd[0]}")
            return EnvironmentExecResult(
                return_code=-1, stdout="", stderr=f"Command not found: {cmd[0]}"
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return_code = process.returncode if process else -1
            return EnvironmentExecResult(
                return_code=return_code, stdout="", stderr=str(e)
            )

    async def start(self):
        """
        Check the docker container executable exists and try to create the container based on the env configuration
        """
        _c = await self._run_cmd(
            [self._executable, "info"], timeout=self._env_config.env_start_timeout
        )
        if _c.return_code != 0:
            raise EnvironmentError("Docker daemon unreachable")
        cmd = [
            self._executable,
            "run",
            "-d",
            "--rm",
            "--init",
            "--name",
            self.env_id,
            "--cpus",
            self._env_config.cpu,
            "--memory",
            self._env_config.mem,
            self._env_config.image,
            "sleep",
            self._env_config.env_timeout,
        ]
        _c = await self._run_cmd(cmd, timeout=self._env_config.env_start_timeout)
        if _c.return_code != 0:
            raise EnvironmentError(f"Docker start failed: {_c.stderr if _c.stderr else _c.stdout}")
        self.container_id = _c.stdout.strip()
        await self._upload_env_artifacts()
        if self._env_config.post_setup_commands:
            cmd = self._env_config.post_setup_commands
            _c = await self.exec(cmd)
            if _c.return_code != 0:
                raise EnvironmentError(
                    f"Docker container post setup command execution failed: {_c.stderr if _c.stderr else _c.stdout}"
                )

    async def _upload_env_artifacts(self):
        """Upload env_artifacts into the container before post_setup_commands run."""
        if not self._env_config.env_artifacts:
            return
        for local_src, container_dst in self._env_config.env_artifacts:
            await self.put_file(local_src, container_dst)

    async def exec(
        self,
        cmd: List[str],
        cwd: str = None,
        env: Dict[str, Any] = None,
        timeout: int = None,
    ):
        """This is used to execute command and return result"""
        try:
            exec_command = [self._executable, "exec"]
            if self._env_config.env_vars:
                for k, v in self._env_config.env_vars.items():
                    exec_command.append("-e", f"{k}={shlex.quote(str(v))}")
            if env and isinstance(env, dict):
                for k, v in env.items():
                    exec_command.extend(["-e", f"{k}={v}"])

            exec_command.append(self.container_id)

            final_cmd = " ".join(cmd)
            if cwd:
                final_cmd = f"cd {cwd} && {final_cmd}"

            exec_command.extend(["bash", "-lc", shlex.quote(final_cmd)])

            response = await self._run_cmd(exec_command, timeout=timeout)

            if response.return_code != 0:
                if "Timeout" in response.stderr:
                    return EnvironmentExecResult(
                        stdout=None,
                        stderr=f"Execution timed out with provided timeout configuration {timeout}",
                        return_code=-1,
                    )
                else:
                    return EnvironmentExecResult(
                        stdout=None,
                        stderr=f"Docker execution Error: {response.stderr}",
                        return_code=-1,
                    )
            return response
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during docker exec: {e}", exc_info=True
            )
            return EnvironmentExecResult(
                stdout=None,
                stderr=f"Docker execution Error: {e}",
                return_code=-1,
            )

    async def put_file(self, source_file: Path | str, target_file: Path | str):
        """This is the used to copy the file from the local to remote"""

        source_file = Path(source_file)
        target_file = Path(target_file)
        remote_dir = target_file.parent
        await self.exec(cmd=["mkdir", "-p", f"{remote_dir}"])

        copy_command = [
            self._executable,
            "cp",
            str(source_file),
            f"{self.container_id}:{str(target_file)}",
        ]

        response = await self._run_cmd(copy_command)

        if response.return_code != 0:
            raise EnvironmentError(
                f"Unable to copy file from local {source_file} to source {target_file} due to:{response.stderr}"
            )

    async def get_file(self, source_file: Path | str, target_file: Path | str,**kwargs):
        """This is the used to copy the file from the remote to local"""

        source_file = Path(source_file)
        target_file = Path(target_file)
        remote_dir = target_file.parent
        if not remote_dir.exists():
            remote_dir.mkdir(mode=_DEFAULT_ENV_FILE_MODE, parents=True, exist_ok=True)

        copy_command = [
            self._executable,
            "cp",
            f"{self.container_id}:{str(source_file)}",
            str(target_file),
        ]

        response = await self._run_cmd(copy_command)

        if response.return_code != 0:
            raise EnvironmentError(
                f"Unable to copy file from container {source_file} to local {target_file} due to:{response.stderr}"
            )

    async def stop(self):
        """This is used to clean up the docker container"""
        try:
            response = await self._run_cmd(
                [self._executable, "rm", "-f", self.container_id]
            )
            if response.return_code != 0:
                raise EnvironmentError(
                    f"Docker Container Deletion Error:{response.stderr}"
                )
        except Exception as e:
            raise EnvironmentError(f"Docker Container Deletion Error:{e}")
