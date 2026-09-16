from agentdist.structures.agent import AgentConfig, AgentResult
from agentdist.structures.executor import (
    ContainerExecConfig,
    ExecConfig,
)
from pydantic import BaseModel, Field, model_validator
from typing import Any, Dict, List, Optional, Callable, Tuple
from uuid import uuid1, uuid4
from enum import Enum


class RunTimeConfig(BaseModel):
    """This config defines the executor environment to be executed"""

    backend: str = Field(..., description="The backend name for the agent to run on")
    backend_config: ContainerExecConfig | ExecConfig = Field(
        ..., description="The backend sandbox exeutor confguration to be executed"
    )


class UDFConfig(BaseModel):
    """The custom function configuration to be used run the custom function using the remote code execution"""

    name: str = Field(..., description="Name of the function to be executed")
    func_code: Dict[str, Any] = Field(
        ..., description="function code to be executed inside the environment"
    )
    runtime_config: RunTimeConfig | None = Field(
        None,
        description="The runtime configuration to be used to create the image and run on the target sandbox",
    )


class DataObjectTypes(Enum):
    """This specifies the execution mode of the data objects"""

    MAP = "map"
    READ = "read"
    STREAM = "stream"


class TaskResult(BaseModel):
    """This is a class to hold the task result"""

    task_id: str = Field(..., description="The unique ID for the task")
    status: int = Field(
        0, description="The status of the task result (0 for success, -1 for failure)"
    )
    raw_output: Optional[str] = None
    raw_error: Optional[str] = None
    parsed_output: Optional[Any] = None
    parsed_error: Optional[Any] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    result_path: Optional[str] = None

    @classmethod
    def create_metadata_task_result(cls, data: Dict[str, Any]):
        """This creates a task result with metadata"""
        return cls(task_id=uuid1().hex, metadata={"data": data})

    @classmethod
    def format_agent_result(cls, task_id: str, result: AgentResult) -> "TaskResult":
        """This formats an AgentResult into a TaskResult"""
        return cls(
            task_id=task_id,
            raw_output=result.stdout,
            raw_error=result.stderr,
            parsed_output=result.trajectory if result.trajectory else None,
            status=result.status,
        )


class TaskContext(BaseModel):
    """This is a class to be used as a context for the task"""

    task_dir: str = Field(..., description="The directory where the task is executed")
    data: TaskResult = Field(..., description="The result of the task")
    task_id: str = Field(..., description="The unique ID for the task")
    stage_id: str = Field(..., description="The unique ID for the stage")


class Stage(BaseModel):
    """This is the result from execution of the DataObject"""

    stage_id: str | None = Field(None, description="The unique ID for the stage")
    results: List[TaskResult] = Field(default_factory=list)
    failed_tasks: List[TaskResult] = Field(default_factory=list)


class StageQueue(BaseModel):
    """This is the queue which combine multiple operation into one"""

    stage_id: str | None = Field(..., description="The unique ID for the stage")
    operation: List[Any] = Field(
        ...,
        description="The operation to be executed in single stage",
        default_factory=list,
    )
    cleanup_environment: bool = Field(
        False, description="Clean the executors after this stage"
    )


class DataObjectConfig(BaseModel):
    """The data object config to be used with the run the task"""

    agent_config: AgentConfig | Callable[[TaskContext], AgentConfig] | None = Field(
        None,
        description="The agent configuration to be run provided agent on provided instruction",
    )
    func_config: UDFConfig | Callable[[TaskContext], UDFConfig]|None = Field(
        None,
        description="The function configuration to be used to run the custom function on the provided input",
    )
    instruction: Callable[[TaskContext], str] | str | None = Field(
        None, description="The instruction is provided the context to the agent"
    )
    result_parser: Callable[[TaskResult], Any] | None = Field(
        None,
        description="The result parser to be used to parse the result from agent and can be used in next stages.",
    )
    artifacts: List[Any] | Callable[[TaskContext], Tuple[str, str]] | None = Field(
        None,
        description="The artifacts location to be copied to task directory before executing the tasks",
    )
    post_exec_callbacks: Dict[str, Callable] | None = Field(
        None,
        description="Callbacks to be executed at different stages of the task execution",
    )

    def to_pydict(self):
        return {
            "agent_config": self.agent_config,
            "func_config": self.func_config,
            "instruction": self.instruction,
            "result_parser": self.result_parser,
            "artifacts": self.artifacts,
            "post_exec_callbacks": self.post_exec_callbacks,
        }


class Task(BaseModel):
    """This is a class to be used as a task in the orchestrator"""

    task_id: str = Field(
        uuid4().hex, description="The unique ID for the orchestrator task"
    )
    stage_id: str
    data_object_config: DataObjectConfig
    parent_result: Optional["TaskResult"] = None

    class Config:
        arbitrary_types_allowed = True

    @model_validator(mode="after")
    def set_task_id(self) -> "Task":
        self.task_id = uuid4().hex
        return self
