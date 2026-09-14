from agentdist.executors.protocol import ExecutionBackend
from agentdist.structures.executor import ExecConfig, EnvironmentExecResult
from agentdist.exceptions import EnvironmentError
import asyncio
from agentdist.observability.logging import Logger
from agentdist.constants import _DEFAULT_ENV_FILE_MODE
from pathlib import Path
from typing import List
from uuid import uuid4
import shlex
from typing import Any, Dict
import tempfile
import os
import shutil
import signal

logger = Logger.get_logger(__name__)


class LocalExecutionBackend(ExecutionBackend):
    """This class acts as contract is used to run the agent in the local subprocess"""

    def __init__(self, env_config: ExecConfig):
        """This is used to specify the environment configuration"""
        self.env_id = uuid4().hex
        self.instance_dir = Path(
            os.path.join(tempfile.gettempdir(), f"instance-{self.env_id}")
        )
        self._env_config = env_config
        self.process_grp = []

    @property
    def env_name(self):
        return f"local_{self.env_id}"

    async def start(self):
        """
        create the local process env directory to start the
        """
        logger.debug(
            f"Starting local execution backend in directory: {self.instance_dir}"
        )
        if self.instance_dir.exists():
            logger.warning(
                f"Instance directory {self.instance_dir} already exists. Removing it."
            )
            shutil.rmtree(self.instance_dir, ignore_errors=True)
        self.instance_dir.mkdir(
            mode=_DEFAULT_ENV_FILE_MODE, parents=True, exist_ok=True
        )
        logger.debug(f"Local instance directory {self.instance_dir} created.")
        await self._upload_env_artifacts()
        if self._env_config.post_setup_commands:
            cmd = self._env_config.post_setup_commands
            for i in cmd:
                _c = await self.exec([i])
                if _c.return_code != 0:
                    await self.stop()
                    raise EnvironmentError(
                        f"Local instance post setup command execution failed: {_c.stderr}"
                    )

    def _clean_env(self) -> dict:
        """Return os.environ with agentdist's conda activation stripped out.
        """
        from agentdist.constants import _DEFAULT_PACKAGE_IN_ENV_DIR
        conda_vars = {
            "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "CONDA_SHLVL",
            "CONDA_EXE", "CONDA_PYTHON_EXE", "CONDA_PROMPT_MODIFIER",
            "_CE_CONDA", "_CE_M",
        }
        env = {k: v for k, v in os.environ.items() if k not in conda_vars}
        if "PATH" in env:
            entries = env["PATH"].split(":")
            entries = [p for p in entries if _DEFAULT_PACKAGE_IN_ENV_DIR not in p]
            env["PATH"] = (
                ":".join(entries)
                or "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            )
        return env

    async def _run_cmd(
        self, cmd: str, timeout: int = None, cwd: str = None, env: dict = None
    ) -> EnvironmentExecResult:
        process = None
        try:
            logger.debug(f"Running command in '{cwd}': {cmd}")
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                preexec_fn=os.setsid,
                cwd=cwd,
                env=env,
            )
            self.process_grp.append(process.pid)
            if timeout:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            else:
                stdout, stderr = await process.communicate()

            logger.debug(f"Command finished with return code {process.returncode}")
            if process.returncode != 0:
                logger.warning(f"Command stderr: {stderr}")

            return EnvironmentExecResult(
                return_code=process.returncode,
                stdout=stdout.decode().strip(),
                stderr=stderr.decode().strip(),
            )
        except asyncio.TimeoutError:
            logger.error(f"Command timed out after {timeout} seconds.")
            if process:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
            return EnvironmentExecResult(return_code=-1, stdout=None, stderr="Timeout")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            return_code = process.returncode if process else -1
            return EnvironmentExecResult(
                return_code=return_code, stdout=None, stderr=str(e)
            )
        finally:
            if process and (process.pid in self.process_grp):
                self.process_grp.remove(process.pid)

    async def _upload_env_artifacts(self):
        """Upload env_artifacts into the local instance before post_setup_commands run."""
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
    ) -> EnvironmentExecResult:
        """This is used to execute command and return result"""

        exec_cwd = self.instance_dir
        if cwd:
            exec_cwd = cwd
        # Environment variables are handled by the shell, so we prepend them to the command
        final_cmd_parts = []
        if env:
            for k, v in env.items():
                final_cmd_parts.append(f"{k}={shlex.quote(str(v))}")

        final_cmd_parts.append(" ".join(cmd))
        final_cmd = " ".join(final_cmd_parts)

        response = await self._run_cmd(
            f"bash -l -c {shlex.quote(final_cmd)}",
            timeout=timeout,
            cwd=exec_cwd,
            env=self._clean_env(),
        )

        if response.return_code != 0:
            logger.error(
                f"Local exec command failed with return code {response.return_code}: {response.stderr}"
            )
            if "Timeout" in response.stderr:
                return EnvironmentExecResult(
                    stdout="",
                    stderr=f"Execution timed out after {timeout} seconds.",
                    return_code=-1,
                )
            return EnvironmentExecResult(
                stdout=response.stdout,
                stderr=f"Local execution error: {response.stderr}",
                return_code=response.return_code,
            )
        return response

    async def put_file(self, source_file: Path | str, target_file: Path | str):
        """This is the used to copy the file from the local to remote"""
        try:
            source_path = Path(source_file)
            target_path = Path(target_file)
            logger.debug(f"Copying '{source_path}' to '{target_path}'")
            if not target_path.parent.exists():
                target_path.parent.mkdir(
                    mode=_DEFAULT_ENV_FILE_MODE, parents=True, exist_ok=True
                )
            shutil.copy(source_path, target_path)
            logger.debug("Copy successful.")
        except Exception as e:
            logger.error(
                f"Failed to copy file '{source_file}' to '{target_file}': {e}",
                exc_info=True,
            )
            raise EnvironmentError(
                f"Unable to copy file from local '{source_file}' to '{target_file}': {e}"
            )

    async def get_file(self, source_file: Path | str, target_file: Path | str,**kwargs):
        """This is the used to copy the file from the remote to local"""
        try:
            source_path = Path(source_file)
            target_path = Path(target_file)
            logger.debug(f"Copying '{source_path}' to '{target_path}'")
            if not target_path.parent.exists():
                target_path.parent.mkdir(
                    mode=_DEFAULT_ENV_FILE_MODE, parents=True, exist_ok=True
                )
            shutil.copy(source_path, target_path)
            logger.debug("Copy successful.")
        except Exception as e:
            logger.error(
                f"Failed to copy file '{source_file}' to '{target_file}': {e}",
                exc_info=True,
            )
            raise EnvironmentError(
                f"Unable to copy file from local '{source_file}' to '{target_file}': {e}"
            )

    async def stop(self):
        """This is used to clean up the running processes and instance directory"""
        logger.debug("Stopping local execution backend...")
        for pid in self.process_grp:
            try:
                logger.debug(f"Terminating process group {pid}...")
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except ProcessLookupError:
                logger.warning(f"Process group {pid} not found, already terminated.")
            except Exception as e:
                logger.error(
                    f"Error terminating process group {pid}: {e}", exc_info=True
                )

        self.process_grp.clear()
        await asyncio.sleep(0.5)
        if self.instance_dir.exists():
            logger.debug(f"Removing instance directory: {self.instance_dir}")
            shutil.rmtree(self.instance_dir, ignore_errors=True)

        logger.debug("Local execution backend stopped.")
