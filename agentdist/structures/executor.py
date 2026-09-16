from pydantic import BaseModel, Field, computed_field
from typing import List, Any, Dict
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


class EnvironmentExecResult(BaseModel):
    """This is a result configuration for the executed environment"""

    stdout: Any
    stderr: Any
    return_code: int
