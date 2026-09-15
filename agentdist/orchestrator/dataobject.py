from pydantic import BaseModel, Field, PrivateAttr, computed_field, model_validator
from agentdist.structures.agent import AgentConfig
from agentdist.structures.dataobject import (
    UDFConfig,
    Stage,
    DataObjectConfig,
    DataObjectTypes,
    TaskContext,
)
from agentdist.observability.logging import Logger
from agentdist.orchestrator.udf import udf
from typing import Any, List, TypeVar, Callable
import shutil
from pathlib import Path
import os

logger = Logger.get_logger(__name__)
AgentContext = TypeVar("AgentContext")


class DataObject(BaseModel):
    """This is the structure holds the distributed object to be executed by Scheduler"""

    parent: Any | None = Field(
        None, description="The parent object to be executed before the child executes"
    )
    type: DataObjectTypes = Field(
        ..., description="The type of the object to be run when the cluster is run"
    )
    operation: str = Field(
        ..., description="The actual name of the function to be run on the data object"
    )
    config: None | DataObjectConfig = Field(
        ..., description="The configuration to be used to run the stage"
    )
    isolate: bool = Field(
        False,
        description="This option to be used to execute the code in separate sandbox environment",
    )
    stage: Stage | None = Field(None, description="The result from the agent result")
    context: AgentContext = Field(
        ..., description="The orchestrator with the context of the job to run the job"
    )
    cleanup_prev_stage: bool = Field(
        False, description="Clean the executors before this stage"
    )
    save_failed: bool = Field(
        False, description="This option to be used to execute the code even if the parent task failed"
    )
    _materialized: bool = PrivateAttr(default=False)

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode="after")
    def validator(self):
        if self.config:
            if self.config.agent_config:
                if hasattr(self.config.agent_config, "backend_config") and getattr(
                    self.config.agent_config, "backend_config"
                ):
                    self.isolate = True
            elif self.config.func_config:
                if self.config.func_config.runtime_config:
                    self.isolate = True
        if (not self.isolate) and self.cleanup_prev_stage:
            self.cleanup_prev_stage = False
        return self

    @computed_field
    @property
    def is_materialized(self) -> bool:
        return self._materialized

    @is_materialized.setter
    def set_materialized(self, value: bool):
        self._materialized = value

    def add_post_exec_callback(self, event: str, func: Callable):
        """Add a callback to the data object"""
        if self.config.post_exec_callbacks is None:
            self.config.post_exec_callbacks = {}
        self.config.post_exec_callbacks[event] = func
        return self

    def map(
        self,
        func: (
            AgentConfig | UDFConfig | Callable[[TaskContext], AgentConfig | UDFConfig]
        ),
        instruction=None,
        parser=None,
        isolate=False,
        prev_operation_env_cleanup=False,
        artifacts: List[str] | Callable[[TaskContext], str] | None = None,
    ):
        """This is the mapping the agent/custom function to be executed with the agent"""
        _config = DataObjectConfig(
            agent_config=(
                func if isinstance(func, AgentConfig) or callable(func) else None
            ),
            func_config=func if isinstance(func, UDFConfig) else None,
            instruction=instruction,
            result_parser=parser,
            artifacts=artifacts,
        )
        return self.__class__(
            parent=self,
            type=DataObjectTypes.MAP,
            operation="map",
            config=_config,
            isolate=isolate,
            context=self.context,
            cleanup_prev_stage=prev_operation_env_cleanup,
        )

    def save(
        self,
        target_path: str,
        full=True,
        save_failed=False,
        custom_func: Callable[[str], None] | None = None,
    ):
        """
        This method saves the output of a task to a target directory.
        NOTE: It generates a UDF on the fly to perform the copy operation.
        """

        @udf()
        def _save(task_dir: str):
            """The task directory is saved into the target directory"""
            if custom_func:
                custom_func(task_dir=task_dir,target_path=target_path)
            else:
                task_dir_name = Path(task_dir).name
                shutil.copytree(task_dir, os.path.join(target_path, task_dir_name), dirs_exist_ok=True)

        return self.__class__(
            parent=self,
            type=DataObjectTypes.MAP,
            operation="save",
            config=DataObjectConfig(
                func_config=_save,
                instruction=lambda x: x.data.metadata["task_dir"].split("://")[-1],
            ),
            isolate=False,
            context=self.context,
            save_failed=save_failed,
        )

    def execute(self):
        """This is the method where the execution of the dag is started"""
        logger.info("Starting DAG execution...")

        self.context.execute(self)
        logger.info("DAG execution finished.")
