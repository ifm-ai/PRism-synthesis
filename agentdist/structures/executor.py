from pydantic import BaseModel, Field, PrivateAttr, model_validator, computed_field
from typing import List, Any, Dict, Callable
from enum import Enum
from agentdist.constants import _DEFAULT_CONTAINER_MEMORY, _DEFAULT_CONTAINER_CORES


class ExecConfig(BaseModel):
    """This is the environment configuration for holding the environment specific configuration"""

    name: str = Field(..., description="The name of the configuration")
    env_vars: Dict[str, Any] = Field(
        ..., description="The environment to be used for the configuration"
    )
    env_start_timeout: int = Field(
        1800,
        description="The environment start timeout where executor to be completed before the environment started",
    )
    env_timeout: str = Field(
        "infinity",
        description="The environment total lifetime timeout where executor to be completed before the environment stopped",
    )
    system_packages: List[str] | None = Field(
        None,
        description="The system to be installed in the environment as part of the setup",
    )
    post_setup_commands: List[str] | None = Field(
        None, description="The post setup commands to be executed"
    )
    env_artifacts: List[tuple[str, str]] | None = Field(
        None,
        description="List of (local_source_path, container_target_path) pairs uploaded used for staging files referenced by COPY in Dockerfiles.",
    )
    skip_remote_env_setup: bool = Field(
        False, description="Skip the agentdist remote env setup of the agent"
    )

    @computed_field
    @property
    def is_offloadble(self) -> bool:
        """This is used to specify whether the operations is offloadable or not based on the configuration"""
        return False


class ContainerExecConfig(ExecConfig):
    """This is specific to container type environment configuration"""

    image: str = Field(..., description="The image to builder the configuration")
    mem: int = Field(
        _DEFAULT_CONTAINER_MEMORY, description="The memory limit to for the container"
    )
    cpu: int = Field(
        _DEFAULT_CONTAINER_CORES,
        description="The amount cpus to be used for the container",
    )
    backend: str = "container"
    secure: bool = Field(
        False,
        description="The secure way of the execution of the container command useful in the apptainer",
    )
    storage_mounts: Dict[str, str] = Field(
        {}, description="The list of the storage mounts to target location"
    )


class KubernetesRuntime(Enum):
    """This is the choices to be used for the kubernetes runtime"""

    default = "default"
    docker = "docker"
    kata = "kata"


class KubernetesVolumeConfig(BaseModel):
    """Configuration for Kubernetes volumes and volume mounts"""

    type: str = Field(..., description="Name of the volume")
    config: Dict[str, Any] = Field(..., description="Configuration for the volume")


class KubernetesExecConfig(BaseModel):
    """This is specific to be used for the kubernetes configuration"""

    backend: str = "kubernetes"
    name: str = Field(..., description="The name of the configuration")
    env_vars: Dict[str, Any] = Field(
        ..., description="The environment to be used for the configuration"
    )
    env_start_timeout: int = Field(
        2900,
        description="The environment start timeout where executor to be completed before the environment started",
    )
    env_timeout: str = Field(
        "infinity",
        description="The environment start timeout where executor to be completed before the environment started",
    )
    system_packages: List[str] | None = Field(
        None,
        description="The system to be installed in the environment as part of the setup",
    )
    post_setup_commands: List[str] | None = Field(
        None, description="The post setup commands to be executed"
    )
    env_artifacts: List[tuple[str, str]] | None = Field(
        None,
        description="List of (local_source_path, container_target_path) pairs uploaded used for staging files referenced by COPY in Dockerfiles.",
    )
    image: str = Field(..., description="The image to builder the configuration")
    image_secret: str | None = Field(
        None, description="The image secret to builder the configuration"
    )
    mem: int = Field(
        _DEFAULT_CONTAINER_MEMORY, description="The memory limit to for the container"
    )
    secure: bool = Field(
        False,
        description="The secure way of the execution of the container command useful in the apptainer",
    )
    security_config: Dict[str, Any] | None = Field(
        None, description="The security context configuration for the kubernetes pod"
    )
    cpu: int = Field(
        _DEFAULT_CONTAINER_CORES,
        description="The amount cpus to be used for the container",
    )
    runtime_class: KubernetesRuntime = Field(
        KubernetesRuntime.default,
        description="This is used to specify the runtime to be used with the kubernetes pod",
    )
    namespace: str = Field(
        "default",
        description="This is used to specify the namespace where kubernetes pod is created",
    )
    service_account_name: str| None = Field(None, description="The service account name to be used for the pod")
    storage_mounts: Dict[str, str] = Field(
        {}, description="The list of the storage mounts to target location"
    )
    storage_volumes: Dict[str, KubernetesVolumeConfig] = Field(
        [], description="The list of the storage volumes to target location"
    )
    offload_pre_env_setup: None|Callable[[], None] = Field(
        None, description="The pre-environment setup function to be offloaded"
    )
    skip_remote_env_setup:bool = Field(False, description="Skip the agentdist remote env setup of the agent")
    _storage_volumes: List[Any] = PrivateAttr(default=[])
    _storage_volumes_mounts: List[Any] = PrivateAttr(default=[])

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode="after")
    def _validate_storage_volumes(self):
        from kubernetes import client
        _check_names = set()
        self._storage_volumes_mounts = []
        self._storage_volumes = []
        if self.storage_volumes:
            for name, volume in self.storage_volumes.items():
                if volume.type not in client.V1Volume.openapi_types:
                    raise ValueError(
                        f"Invalid volume type: {volume.type}, should be one of {list(client.V1Volume.openapi_types.keys())}"
                    )

                volume_class = getattr(
                    client, client.V1Volume.openapi_types[volume.type]
                )
                if set(volume.config.keys()) != set(volume_class.openapi_types.keys()):
                    raise ValueError(
                        f"Invalid volume config: {volume.config}, should be one of {list(volume_class.openapi_types.keys())}"
                    )
                self._storage_volumes.append(
                    client.V1Volume(
                        **{"name": name, volume.type: volume_class(**volume.config)}
                    )
                )
                _check_names.add(name)
        # Deleting the keys which are not required
        for i in self.storage_mounts.keys():
            if i in _check_names:
                self._storage_volumes_mounts.append(
                    client.V1VolumeMount(
                        **{"name": i, "mount_path": self.storage_mounts[i]}
                    )
                )

        return self

    @computed_field
    @property
    def get_volume_mounts(self) -> List[Any]:
        return self._storage_volumes_mounts

    @computed_field
    @property
    def get_volumes(self) -> List[Any]:
        return self._storage_volumes

    @classmethod
    def empty_config(cls, **kwargs):
        return cls(
            name="empty",
            backend="kubernetes",
            env_vars=kwargs.get("env_vars", {}),
            namespace=kwargs.get("namespace", "default"),
            image="empty",
        )

    @computed_field
    @property
    def is_offloadble(self) -> bool:
        """This is used to specify whether the operations is offloadable or not based on the configuration"""
        return True


class EnvironmentExecResult(BaseModel):
    """This is a result configuration for the executed environment"""

    stdout: Any
    stderr: Any
    return_code: int
