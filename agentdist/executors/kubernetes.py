from kubernetes import client, config
from kubernetes.client.rest import ApiException
from agentdist.exceptions import EnvironmentError
from kubernetes.stream import stream
from typing import List
from uuid import uuid4
import shlex
from typing import Any, Optional, Dict
import tarfile
from pathlib import Path
import io
import asyncio
import os
import base64
from urllib.parse import urlparse
from agentdist.structures.executor import (
    KubernetesExecConfig,
    EnvironmentExecResult,
    KubernetesRuntime,
)
from agentdist.executors.protocol import ExecutionBackend
from agentdist.constants import _DEFAULT_ENV_FILE_MODE
from agentdist.observability.logging import Logger
from copy import deepcopy
logger = Logger.get_logger(__name__)


class Singleton(type):
    """This is the design pattern for the singleton class, where single object exists"""

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class KubeExecutionBackend(ExecutionBackend):
    """This  class acts as contract is used to run the agent on the kubernetes backend"""

    def __init__(self, env_config: KubernetesExecConfig, extra_labels: Optional[Dict[str, str]] = None):
        """This is used to specify the environment configuration"""
        self._env_config = env_config
        self._extra_labels = extra_labels
        self.env_id = uuid4().hex
        self.pod_name = f"pod-{self.env_id}"
        try:
            logger.debug("Loading Kubernetes configuration...")
            config.load_kube_config()
            configuration = client.Configuration.get_default_copy()
            configuration.proxy = None
            # below i added where websocket by executing the exec function api_namespace_connect_pod is hitting proxy, i want to avoid that
            if configuration.host:
                host = urlparse(configuration.host).hostname
                if host:
                    for key in ["no_proxy", "NO_PROXY"]:
                        val = os.environ.get(key, "")
                        parts = val.split(",") if val else []
                        if host not in parts:
                            parts.append(host)
                            os.environ[key] = ",".join(parts)
            client.Configuration.set_default(configuration)
            self._client_api = client.CoreV1Api()
            self._batch_api = client.BatchV1Api()
            logger.debug("Kubernetes configuration loaded successfully.")
        except config.ConfigException as e:
            try:
                config.load_incluster_config()
                configuration = client.Configuration.get_default_copy()
                configuration.proxy = None
                if configuration.host:
                    host = urlparse(configuration.host).hostname
                    if host:
                        for key in ["no_proxy", "NO_PROXY"]:
                            val = os.environ.get(key, "")
                            parts = val.split(",") if val else []
                            if host not in parts:
                                parts.append(host)
                                os.environ[key] = ",".join(parts)
                client.Configuration.set_default(configuration)
                self._client_api = client.CoreV1Api()
                self._batch_api = client.BatchV1Api()
                logger.debug("Kubernetes configuration loaded successfully.")
            except config.ConfigException as e:
                logger.error(
                    f"Could not load Kubernetes configuration: {e}", exc_info=True
                )
                raise EnvironmentError(
                    f"Kubernetes executor initialization failed: Could not load configuration. {e}"
                )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during Kubernetes initialization: {e}",
                exc_info=True,
            )
            raise EnvironmentError(
                f"Kubernetes executor initialization failed due to an unexpected error: {e}"
            )

    @property
    def client(self):
        return self._client_api

    @property
    def batch_client(self):
        return self._batch_api

    @property
    def env_name(self):
        return f"kube_{self.env_id}"

    async def start(self):
        """
        This is used to start the environment with the provided env configuration
        Steps as follows:
            1. setup the pod object with the provided environment configuration
            2. then try creating the pod if exists, go forward to delete and try recreating else raise error
            3. trying the creating the pod is successfull and then try until pod is running
        """
        logger.debug(
            f"Starting Kubernetes pod '{self.pod_name}' in namespace '{self._env_config.namespace}'..."
        )

        requests = {
            "cpu": str(self._env_config.cpu),
            "memory": f"{self._env_config.mem}Gi",
        }
        security_context = None
        if self._env_config.secure:
            if not self._env_config.security_config:
                logger.warning(
                    "Security config is not provided but secure mode is enabled."
                )
            else:
                security_config = deepcopy(self._env_config.security_config)
                if "capabilities" in security_config:
                    capabilities = client.V1Capabilities(
                        **security_config["capabilities"]
                    )
                    security_config["capabilities"] = capabilities
                 
                security_context = client.V1SecurityContext(
                    **security_config
                )
        pod = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(
                name=self.pod_name,
                namespace=self._env_config.namespace,
                labels={
                    "app": "agent-sandbox",
                    "env_id": self.env_id,
                    "environment": self._env_config.name,
                    **(self._extra_labels or {}),
                },
            ),
            spec=client.V1PodSpec(
                service_account_name=self._env_config.service_account_name,
                image_pull_secrets=(
                    [client.V1LocalObjectReference(name=self._env_config.image_secret)]
                    if self._env_config.image_secret
                    else None
                ),
                containers=[
                    client.V1Container(
                        name="main",
                        image=self._env_config.image,
                        command=["sleep", "infinity"],
                        resources=client.V1ResourceRequirements(
                            requests=requests, limits=requests
                        ),
                        volume_mounts=self._env_config.get_volume_mounts,
                        env=[
                            client.V1EnvVar(name=k, value=str(v))
                            for k, v in self._env_config.env_vars.items()
                        ],
                        security_context=security_context,
                    )
                ],
                restart_policy="Never",
                runtime_class_name=(
                    self._env_config.runtime_class.value
                    if self._env_config.runtime_class != KubernetesRuntime.default
                    else None
                ),
                volumes=self._env_config.get_volumes,
            ),
        )

        try:
            logger.debug(f"Creating pod '{self.pod_name}'...")
            await asyncio.to_thread(
                self._client_api.create_namespaced_pod,
                body=pod,
                namespace=self._env_config.namespace,
            )
        except ApiException as e:
            # Pod already exists
            if e.status == 409:
                logger.warning(
                    f"Pod '{self.pod_name}' already exists. Deleting and recreating."
                )
                try:
                    await self.stop()
                    for _ in range(60):
                        await asyncio.sleep(1)
                        try:
                            await asyncio.to_thread(
                                self._client_api.read_namespaced_pod,
                                name=self.pod_name,
                                namespace=self._env_config.namespace,
                            )
                        except ApiException as read_e:
                            if read_e.status == 404:
                                logger.debug("Existing pod deleted successfully.")
                                break
                    else:
                        raise EnvironmentError(
                            f"Failed to delete existing pod '{self.pod_name}' in time."
                        )

                    logger.debug(f"Recreating pod '{self.pod_name}'...")
                    await asyncio.to_thread(
                        self._client_api.create_namespaced_pod,
                        body=pod,
                        namespace=self._env_config.namespace,
                    )
                except Exception as delete_recreate_e:
                    raise EnvironmentError(
                        f"Failed to recreate pod '{self.pod_name}': {delete_recreate_e}"
                    )
            else:
                raise EnvironmentError(
                    f"Unable to create pod '{self.pod_name}': {e.reason}"
                )
        try:
            logger.debug(f"Waiting for pod '{self.pod_name}' to become ready...")
            await self._check_pod_ready(self._env_config.env_start_timeout)
        except EnvironmentError as e:
            await self.stop()
            raise e

        logger.debug(f"Pod '{self.pod_name}' is running.")
        await self._upload_env_artifacts()
        if self._env_config.post_setup_commands:
            cmd = self._env_config.post_setup_commands
            for i in cmd:
                _c = await self.exec([i])
                if _c.return_code != 0:
                    await self.stop()
                    raise EnvironmentError(
                        f"Kubernetes pod post setup command execution failed: {_c.stderr}"
                    )

    async def _upload_env_artifacts(self):
        """Upload env_artifacts into the pod before post_setup_commands run."""
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
        if not self.pod_name:
            raise EnvironmentError("Pod not started. Call start() first.")

        env_parts = []
        if env:
            for k, v in env.items():
                env_parts.append(f"{k}={shlex.quote(str(v))}")

        inner_cmd = " ".join(cmd)
        if cwd:
            inner_cmd = f"cd {shlex.quote(cwd)} && {inner_cmd}"
        inner_cmd = (
            f'export {" ".join(env_parts)};{inner_cmd}' if env_parts else inner_cmd
        )
        inner_cmd = f"bash -c {shlex.quote(inner_cmd)}"

        final_cmd = ["sh", "-c", inner_cmd]
        logger.debug(f"Executing command in pod '{self.pod_name}': {inner_cmd}")

        try:
            response = await asyncio.to_thread(
                stream,
                self._client_api.connect_get_namespaced_pod_exec,
                name=self.pod_name,
                namespace=self._env_config.namespace,
                command=final_cmd,
                stdin=False,
                stdout=True,
                stderr=True,
                tty=False,
                _preload_content=False,
            )

            stdout, stderr = await asyncio.wait_for(
                asyncio.to_thread(self.read_stream, response), timeout=timeout
            )

            response.run_forever(timeout=0)
            response.close()
            return_code = response.returncode if response else 0
            if return_code != 0:
                logger.error(f"Kubernetes exec command failed. Stderr: {stderr}")

            return EnvironmentExecResult(
                stdout=stdout, stderr=stderr, return_code=return_code
            )
        except asyncio.TimeoutError:
            logger.error(
                f"Execution in pod '{self.pod_name}' timed out after {timeout} seconds."
            )
            return EnvironmentExecResult(
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds.",
                return_code=-1,
            )
        except ApiException as e:
            logger.error(
                f"API error during exec in pod '{self.pod_name}': {e.reason}",
                exc_info=True,
            )
            return EnvironmentExecResult(
                stdout="",
                stderr=f"Kubernetes execution API Error: {e.reason}",
                return_code=-1,
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during exec in pod '{self.pod_name}': {e}",
                exc_info=True,
            )
            return EnvironmentExecResult(
                stdout="",
                stderr=f"Kubernetes execution unknown error: {e}",
                return_code=-1,
            )

    def read_stream(self, response: Any):
        """synchronously reads stdout and stderr from a Kubernetes stream."""
        stdout = ""
        stderr = ""
        while response.is_open():
            response.update(timeout=1)
            if response.peek_stdout():
                out = response.read_stdout()
                stdout += out
            if response.peek_stderr():
                err = response.read_stderr()
                stderr += err
        return stdout, stderr

    async def put_file(self, source_file: Path | str, target_file: Path | str):
        """This is the used to copy the file from the local to remote using a tar stream."""
        source_path = Path(source_file)
        target_path = Path(target_file)
        remote_dir = target_path.parent

        logger.debug(f"Copying '{source_path}' to pod '{self.pod_name}:{target_path}'")

        await self.exec(cmd=["mkdir", "-p", str(remote_dir)])

        copy_command = ["tar", "xf", "-", "-C", str(remote_dir)]

        try:
            _buffer = io.BytesIO()
            with tarfile.open(fileobj=_buffer, mode="w") as tar:
                tar.add(name=str(source_path), arcname=target_path.name)
            _buffer.seek(0)

            response = await asyncio.to_thread(
                stream,
                self._client_api.connect_get_namespaced_pod_exec,
                name=self.pod_name,
                namespace=self._env_config.namespace,
                command=copy_command,
                stdin=True,
                stdout=True,
                stderr=True,
                tty=False,
                _preload_content=False,
            )
            response.write_stdin(_buffer.read())
            response.run_forever(timeout=1)
            response.close()
            logger.debug("File copy to pod completed.")
        except Exception as e:
            logger.error(
                f"Error during put_file to pod '{self.pod_name}': {e}", exc_info=True
            )
            raise EnvironmentError(f"Failed to copy file to pod: {e}")

    async def get_file(
        self, source_file: Path | str, target_file: Path | str, binary=False, **kwargs
    ):
        """This is the used to copy the file from the remote to local"""
        source_path = Path(source_file)
        target_path = Path(target_file)

        logger.debug(
            f"Copying from pod '{self.pod_name}:{source_path}' to local '{target_path}'"
        )

        if not target_path.parent.exists():
            logger.debug(f"Creating local directory '{target_path.parent}'")
            target_path.parent.mkdir(
                mode=_DEFAULT_ENV_FILE_MODE, parents=True, exist_ok=True
            )

        # copy_command = ["/bin/sh", "-c", f"tar cPf - {shlex.quote(str(source_path))} 2> /dev/null| base64"]
        copy_command = ["tar", "cf", "-", str(source_path), "2> /dev/null"]
        response = await asyncio.to_thread(
            stream,
            self._client_api.connect_get_namespaced_pod_exec,
            name=self.pod_name,
            namespace=self._env_config.namespace,
            command=copy_command,
            stdin=True,
            stdout=True,
            stderr=True,
            tty=False,
            _preload_content=False,
            binary=binary,
        )

        try:
            # _buffer = []
            _buffer = io.BytesIO()
            # I have this websocket issue where it closes, i need the stdout every thing
            while response.is_open():
                response.update(timeout=1)
                if response.peek_stdout():
                    data = response.read_stdout()
                    _buffer.write(data)
            # if response.peek_stdout():
            #     data = response.read_stdout()
            #     _buffer.append(data)

            if response.peek_stdout():
                data = response.read_stdout()
                _buffer.write(data)
            _buffer.flush()
            _buffer.seek(0)
            # # 1. Join the chunks and strip any accidental whitespace/newlines
            # b64_string = "".join(_buffer).replace('\n', '').replace('\r', '').strip()

            # # 2. Automatically fix missing padding
            # missing_padding = len(b64_string) % 4
            # if missing_padding:
            #     b64_string += '=' * (4 - missing_padding)
            # _buffer = base64.b64decode(b64_string)
            # response.close()
            # _buffer = io.BytesIO(_buffer)
            with tarfile.open(fileobj=_buffer, mode="r") as tar:
                for member in tar.getmembers():
                    if (member.name == str(source_path)) or (
                        member.name == str(source_path).lstrip("/")
                    ):
                        member.name = target_path.name
                        tar.extract(member, path=target_path.parent)
                        break
            logger.debug(f"Successfully copied file from pod to '{target_path}'.")
        except Exception as e:
            logger.error(
                f"Error during get_file from pod '{self.pod_name}': {e}", exc_info=True
            )
            raise EnvironmentError(f"Failed to get file from pod: {e}")

    async def _check_pod_ready(self, timeout: int = 100):
        """
        This method checks the pod is running state
        `This is LLM Generated`"""
        logger.debug(
            f"Waiting for pod '{self.pod_name}' to become ready (timeout: {timeout}s)..."
        )
        check_try_again = timeout
        for i in range(timeout):
            try:
                pod_status = await asyncio.to_thread(
                    self._client_api.read_namespaced_pod_status,
                    name=self.pod_name,
                    namespace=self._env_config.namespace,
                )

                phase = pod_status.status.phase
                #logger.debug(
                #    f"Pod '{self.pod_name}' status: {phase} (check {i+1}/{timeout})"
                #)

                if phase == "Running":
                    return  # Success
                elif phase in ["Failed", "Error", "Unknown"]:
                    error_details = self._get_pod_failure(pod_status)
                    logger.error(
                        f"Pod '{self.pod_name}' entered a failed state: {error_details}"
                    )
                    raise EnvironmentError(f"Pod failed to start: {error_details}")
                elif phase == "Pending":
                    # Check for image pull errors, which are common pending reasons
                    if pod_status.status.container_statuses:
                        for c in pod_status.status.container_statuses:
                            if c.state and c.state.waiting:
                                reason = c.state.waiting.reason
                                message = c.state.waiting.message
                                if reason and (
                                    "ImagePullBackOff" in reason
                                    or "ErrImagePull" in reason
                                ):
                                    if check_try_again > 0:
                                        
                                        check_try_again -= 1
                                        break
                                    else:
                                        logger.warning(
                                            f"Pod '{self.pod_name}' is pending due to image pull error: {reason} - {message}"
                                        )
                                        raise EnvironmentError(
                                            f"Failed to pull image '{c.image}': {reason} - {message}"
                                        )
                                else:
                                    check_try_again = 10
            except ApiException as e:
                if e.status != 404:
                    logger.error(
                        f"API error while checking pod status: {e.reason}",
                        exc_info=True,
                    )
                    raise EnvironmentError(f"There is an API Error: {e.reason}")

            await asyncio.sleep(1)

        raise EnvironmentError(
            f"Pod '{self.pod_name}' did not become ready within {timeout} seconds."
        )

    def _get_pod_failure(self, pod) -> str:
        """
        Get a summary of pod failure reasons.
        `This is LLM Generated`
        """
        reasons = []

        if pod.status.reason:
            reasons.append(f"Reason: {pod.status.reason}")
        if pod.status.message:
            reasons.append(f"Message: {pod.status.message}")

        if pod.status.container_statuses:
            for c_status in pod.status.container_statuses:
                if c_status.state and c_status.state.waiting:
                    reasons.append(
                        f"Container '{c_status.name}' is waiting: {c_status.state.waiting.reason} - {c_status.state.waiting.message}"
                    )
                elif c_status.state and c_status.state.terminated:
                    reasons.append(
                        f"Container '{c_status.name}' terminated: {c_status.state.terminated.reason} "
                        f"(exit code {c_status.state.terminated.exit_code}) - {c_status.state.terminated.message}"
                    )

        return "; ".join(reasons) if reasons else "Unknown error"

    async def stop(self):
        """This is used to clean up the kubernetes pod"""
        logger.debug(f"Stopping pod '{self.pod_name}'...")
        try:
            await asyncio.to_thread(
                self._client_api.delete_namespaced_pod,
                name=self.pod_name,
                namespace=self._env_config.namespace,
                body=client.V1DeleteOptions(grace_period_seconds=0),
            )

            # Wait for pod to be deleted
            for _ in range(60):
                await asyncio.sleep(1)
                try:
                    await asyncio.to_thread(
                        self._client_api.read_namespaced_pod,
                        name=self.pod_name,
                        namespace=self._env_config.namespace,
                    )
                except ApiException as e:
                    if e.status == 404:
                        logger.debug(f"Pod '{self.pod_name}' deleted successfully.")
                        return

            logger.warning(
                f"Pod '{self.pod_name}' was not confirmed as deleted within the timeout."
            )

        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Stop called, but pod '{self.pod_name}' was not found.")
            else:
                logger.error(
                    f"API error while deleting pod '{self.pod_name}': {e.reason}",
                    exc_info=True,
                )
                raise EnvironmentError(f"Pod Deletion Error:{e.reason}")
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during pod stop: {e}", exc_info=True
            )
            raise EnvironmentError(f"An unexpected error occurred during pod stop: {e}")

    def create_config(self, name: str, content: Any, labels:Dict[str, str] = None):
        """This is used to create the kubernetes config based on the content passed"""
        try:
            config_map = client.V1ConfigMap(
                api_version="v1",
                kind="ConfigMap",
                metadata=client.V1ObjectMeta(
                    name=name, namespace=self._env_config.namespace, labels=labels if labels else None
                ),
                data=content,
            )
            self._client_api.create_namespaced_config_map(
                namespace=self._env_config.namespace, body=config_map
            )
            return EnvironmentExecResult(stdout="", stderr="", return_code=0)
        except Exception as e:
            return EnvironmentExecResult(stdout="", stderr=str(e), return_code=-1)

    def create_job(
        self,
        job_name: str,
        command: str,
        volumes: Any = [],
        volume_mounts: Any = [],
        job_labels: Dict[str, str] = {},
    ):
        """This method creates the job to be executed"""
        try:
            security_context = None
            if self._env_config.secure:
                if not self._env_config.security_config:
                    logger.warning(
                        "Security config is not provided but secure mode is enabled."
                    )
                else:
                    security_config = deepcopy(self._env_config.security_config)
                    if "capabilities" in security_config:
                        capabilities = client.V1Capabilities(
                            **security_config["capabilities"]
                        )
                        security_config["capabilities"] = capabilities
                    
                    security_context = client.V1SecurityContext(
                        **security_config
                    )
            requests = {
                "cpu": str(self._env_config.cpu),
                "memory": f"{self._env_config.mem}Gi",
            }
            job = client.V1Job(
                api_version="batch/v1",
                kind="Job",
                metadata=client.V1ObjectMeta(
                    name=job_name,
                    namespace=self._env_config.namespace,
                    labels=job_labels,
                ),
                spec=client.V1JobSpec(
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(
                            labels=job_labels,
                        ),
                        spec=client.V1PodSpec(
                            service_account_name=self._env_config.service_account_name,
                            image_pull_secrets=(
                                [
                                    client.V1LocalObjectReference(
                                        name=self._env_config.image_secret
                                    )
                                ]
                                if self._env_config.image_secret
                                else None
                            ),
                            containers=[
                                client.V1Container(
                                    name="main",
                                    image=self._env_config.image,
                                    command=command,
                                    resources=client.V1ResourceRequirements(
                                        requests=requests, limits=requests
                                    ),
                                    volume_mounts=volume_mounts + self._env_config.get_volume_mounts,
                                    env=[
                                        client.V1EnvVar(name=k, value=str(v))
                                        for k, v in self._env_config.env_vars.items()
                                    ],
                                    security_context=security_context,
                                )
                            ],
                            restart_policy="Never",
                            runtime_class_name=(
                                self._env_config.runtime_class.value
                                if self._env_config.runtime_class
                                != KubernetesRuntime.default
                                else None
                            ),
                            volumes=volumes + self._env_config.get_volumes,
                        )
                    ),
                    ttl_seconds_after_finished=60,  # Auto cleanup after 1 hour
                    backoff_limit=0,
                ),
            )
            self._batch_api.create_namespaced_job(
                namespace=self._env_config.namespace, body=job
            )
            return EnvironmentExecResult(stdout="", stderr="", return_code=0)

        except Exception as e:
            logger.error(f"Failed to create job {job_name} due to error: {e}", exc_info=True)
            return EnvironmentExecResult(stdout="", stderr=str(e), return_code=-1)

    def delete_config(self, name: str):
        """Deletes a ConfigMap"""
        try:
            self._client_api.delete_namespaced_config_map(
                name=name, namespace=self._env_config.namespace
            )
            return EnvironmentExecResult(stdout="", stderr="", return_code=0)
        except ApiException as e:
            if e.status == 404:
                return EnvironmentExecResult(stdout="", stderr="", return_code=0)
            return EnvironmentExecResult(stdout="", stderr=str(e), return_code=-1)
        except Exception as e:
            return EnvironmentExecResult(stdout="", stderr=str(e), return_code=-1)

    def delete_job(self, job_name: str):
        """Deletes a Job"""
        try:
            self._batch_api.delete_namespaced_job(
                name=job_name,
                namespace=self._env_config.namespace,
                body=client.V1DeleteOptions(propagation_policy="Foreground"),
            )
            return EnvironmentExecResult(stdout="", stderr="", return_code=0)
        except ApiException as e:
            if e.status == 404:
                return EnvironmentExecResult(stdout="", stderr="", return_code=0)
            return EnvironmentExecResult(stdout="", stderr=str(e), return_code=-1)
        except Exception as e:
            return EnvironmentExecResult(stdout="", stderr=str(e), return_code=-1)
