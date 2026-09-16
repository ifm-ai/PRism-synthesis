from agentdist.executors.docker import DockerExecutionBackend
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
import tarfile
import io
import tempfile

logger = Logger.get_logger(__name__)


class ApptainerExecutionBackend(DockerExecutionBackend):
    """This class acts as contract is used to run the agent in the apptainer executor"""

    def __init__(self, env_config: ContainerExecConfig):
        """This is used to specify the environment configuration"""
        super().__init__(env_config)
        self._executable = "apptainer"
        self.env_id = uuid4().hex
        # self.instance_name =  f"instance-{self.env_id[:10]}" # Changed due to instance start not working with the limited RAM Space
        self.instance_name = str(
            Path(tempfile.gettempdir()) / f"instance-{self.env_id}"
        )

    @property
    def env_name(self):
        return f"apptainer_{self.env_id}"

    async def start(self):
        """
        Check the apptainer container executable exists and try to create the container based on the env configuration
        """
        logger.debug("Starting Apptainer execution backend...")
        _c = await self._run_cmd(
            [self._executable, "version"], timeout=self._env_config.env_start_timeout
        )
        if _c.return_code != 0:
            raise EnvironmentError(f"Apptainer executable not available: {_c.stderr if _c.stderr else _c.stdout}")

        logger.debug(
            f"Starting instance '{self.instance_name}' with image '{self._env_config.image}'"
        )
        # apptainer instance start not working because of the ram space issue, so switching to the sandbox directory
        # cmd = [
        #     self._executable,
        #     "instance",
        #     "start",
        #     "--writable-tmpfs",
        #     "--containall",
        #     "--no-home",
        #     f"docker://{self._env_config.image}",
        #     self.instance_name,
        # ]
        cmd = [
            self._executable,
            "build",
            "--sandbox",
            self.instance_name,
            f"{self._env_config.image}",
        ]
        if self._env_config.secure:
            cmd = ["unshare", "-r"] + cmd
        _c = await self._run_cmd(cmd, timeout=self._env_config.env_start_timeout)
        if _c.return_code != 0:
            raise EnvironmentError(f"Apptainer container start failed: {_c.stderr}")
        await self._upload_env_artifacts()
        if self._env_config.post_setup_commands:
            cmd = self._env_config.post_setup_commands
            for i in cmd:
                _c = await self.exec([i])
                if _c.return_code != 0:
                    await self.stop()
                    raise EnvironmentError(
                        f"Apptainer container post setup command {i} execution failed: {_c.stderr}"
                    )
        logger.debug(f"Apptainer instance '{self.instance_name}' started successfully.")

    async def exec(
        self,
        cmd: List[str],
        cwd: str = None,
        env: Dict[str, Any] = None,
        timeout: int = None,
        decode_bytes = True
    ) -> EnvironmentExecResult:
        """This is used to execute command and return result"""
        env_parts = []
        if env:
            for k, v in env.items():
                env_parts.append(f"--env {k}={shlex.quote(str(v))}")
        if self._env_config.env_vars:
            for k, v in self._env_config.env_vars.items():
                env_parts.append(f"--env {k}={shlex.quote(str(v))}")

        inner_cmd = " ".join(cmd)
        if cwd:
            inner_cmd = f"cd {shlex.quote(cwd)} && {inner_cmd}"
        inner_cmd = f"bash -c {shlex.quote(inner_cmd)}"
        env_parts = " ".join(env_parts)
        if self._env_config.storage_mounts:
            for src, dest in self._env_config.storage_mounts.items():
                env_parts = f"--bind {src}:{dest} {env_parts}"
        exec_command = [
            self._executable,
            "exec",
            "--no-eval",
            "--containall",
            "--no-home",
            # "--writable-tmpfs",
            "--writable",
            env_parts,
            # f"instance://{self.instance_name}",
            self.instance_name,
            inner_cmd,
        ]
        try:
            if self._env_config.secure:
                exec_command = ["unshare", "-r"] + exec_command
            response = await self._run_cmd(exec_command, timeout=timeout,decode_bytes=decode_bytes)

            if response.return_code != 0:
                logger.error(
                    f"Exec command failed with return code {response.return_code}: {response.stderr if response.stderr else response.stdout}"
                )
                if "Timeout" in response.stderr:
                    return EnvironmentExecResult(
                        stdout="",
                        stderr=f"Execution timed out after {timeout} seconds.",
                        return_code=-1,
                    )
                else:
                    return EnvironmentExecResult(
                        stdout=None,
                        stderr=f"Apptainer execution Error: {response.stderr if response.stderr else response.stdout}",
                        return_code=-1,
                    )
            return response

        except Exception as e:
            logger.error(f"Exec command failed with error {e}", exc_info=True)
            return EnvironmentExecResult(
                stdout=None,
                stderr=f"Apptainer execution Error: {e}",
                return_code=-1,
            )

    async def put_file(self, source_file: Path | str, target_file: Path | str):
        """This is the used to copy the file from the local to remote"""
        source_path = Path(source_file)
        target_path = Path(target_file)
        remote_dir = target_path.parent

        logger.debug(f"Copying '{source_path}' to '{self.instance_name}:{target_path}'")

        c = await self.exec(cmd=["mkdir", "-p", str(remote_dir)])
        if c.return_code != 0:
            raise EnvironmentError(f"Apptainer mkdir failed: {c.stderr if c.stderr else c.stdout}")
        env_parts = []
        if self._env_config.env_vars:
            for k, v in self._env_config.env_vars.items():
                env_parts.append(f"--env {k}={shlex.quote(str(v))}")
        cmd = shlex.quote(
            " ".join(
                ["tar", "xf", "-", "--no-same-owner", "-C", str(target_path.parent)]
            )
        )
        env_parts = " ".join(env_parts)
        if self._env_config.storage_mounts:
            for src, dest in self._env_config.storage_mounts.items():
                env_parts = f"--bind {src}:{dest} {env_parts}"
        copy_command = f"bash -c {cmd}"
        command = [
            self._executable,
            "exec",
            "--no-eval",
            "--containall",
            "--no-home",
            # "--writable-tmpfs",
            "--writable",
            env_parts,
            # f"instance://{self.instance_name}",
            self.instance_name,
            copy_command,
        ]

        process = None
        try:
            if self._env_config.secure:
                command = ["unshare", "-r"] + command
            with io.BytesIO() as _buffer:
                with tarfile.open(fileobj=_buffer, mode="w") as tar:
                    tar.add(name=str(source_path), arcname=target_path.name)
                _buffer.seek(0)
                command = " ".join(command)
                logger.debug(f"Running command: {command}")
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate(input=_buffer.read())

                if process.returncode != 0:
                    raise EnvironmentError(
                        f"Failed to copy file to apptainer: {stderr.decode()}"
                    )
            logger.debug(f"Successfully copied file to '{target_path}' in instance.")
        except Exception as e:
            logger.error(
                f"An error occurred during put_file to apptainer: {e}", exc_info=True
            )
            raise EnvironmentError(
                f"Unable to copy file from local '{source_path}' to instance '{target_path}': {e}"
            )

    async def get_file(self, source_file: Path | str, target_file: Path | str,**kwargs):
        """This is the used to copy the file from the remote to local"""
        source_path = Path(source_file)
        target_path = Path(target_file)

        logger.debug(f"Copying '{self.instance_name}:{source_path}' to '{target_path}'")

        if not target_path.parent.exists():
            logger.debug(f"Creating local directory '{target_path.parent}'")
            target_path.parent.mkdir(
                mode=_DEFAULT_ENV_FILE_MODE, parents=True, exist_ok=True
            )

        copy_command = ["tar", "cf", "-", str(source_path)]

        response = await self.exec(copy_command,decode_bytes=False)
        if response.return_code != 0:
            stderr = (
                response.stderr.decode()
                if isinstance(response.stderr, bytes)
                else response.stderr
            )
            raise EnvironmentError(
                f"Unable to create tar archive in apptainer for '{source_path}': {stderr}"
            )

        try:
            _buffer = io.BytesIO(response.stdout)
            with tarfile.open(fileobj=_buffer, mode="r") as tar:
                for member in tar.getmembers():
                    if (member.name == source_path) or (member.name == str(source_path).lstrip("/")):
                        member.name = target_path.name
                        tar.extract(member, path=target_path.parent)
                        break
            logger.debug(f"Successfully copied file from instance to '{target_path}'.")
        except Exception as e:
            raise EnvironmentError(f"Failed to extract tar archive from apptainer: {e}")

    async def stop(self):
        """This is used to clean up the apptainer instance"""
        logger.debug(f"Stopping instance '{self.instance_name}'...")
        try:
            # response = await self._run_cmd(
            #     [self._executable, "instance", "stop", "--force", self.instance_name]
            # )
            response = await self._run_cmd(["rm", "-rf", self.instance_name])
            if response.return_code != 0:
                raise EnvironmentError(
                    f"Failed to stop apptainer instance '{self.instance_name}': {response.stderr}"
                )
            logger.debug(f"Instance '{self.instance_name}' stopped successfully.")
        except Exception as e:
            logger.error(
                f"An error occurred while stopping instance '{self.instance_name}': {e}",
                exc_info=True,
            )
            raise EnvironmentError(f"Apptainer instance deletion error: {e}")
