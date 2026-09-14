from pydantic import BaseModel, Field
from typing import List, Dict, Any

from agentdist.structures.executor import (
    ContainerExecConfig,
    ExecConfig,
)

class AgentContext(BaseModel):
    """The context to be passed to the agent"""

    task_dir: str = Field(
        ..., description="The directory where the task artifacts are saved executed"
    )
    env_vars: Dict[str, Any] | None = Field(
        None, description="The environment to be used for the configuration"
    )
    run_dir: str | None = Field(
        None, description="The task context directory where the task needs to run"
    )


class AgentTrajectoryMetadata(BaseModel):
    """The agent trajectory method to be used for the capturing the agent info details"""

    session_id: str = Field(..., description="This is session information")


class AgentInfo(BaseModel):
    """The agent info method to be used for the capturing the agent info details"""

    name: str = Field(
        ...,
        description="This is the agent info to be used for the identifying the agent",
    )
    version: str = Field(..., description="This is the agent version if any")


class AgentTrajectoryMetrics(BaseModel):
    """The agent trajectory metrics to be used for the capturing the agent info details"""
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int

class AgentTrajectoryTool(BaseModel):
    """The tool used by the agent in the trajectory"""

    name: str
    tool_id: str
    arguments: Any
    title: str|None
    result: str | None
    duration: int|None
    status: str|None

class AgentTrajectoryStep(BaseModel):
    """This is the step between the user and assistant"""

    step_id: str
    role: str
    duration: int
    timestamp: str | int
    model_name: str
    message: str
    reasoning_content: str
    tool_call: List[AgentTrajectoryTool] = Field(default_factory=list)
    metrics: AgentTrajectoryMetrics


class AgentTrajectory(BaseModel):
    """The agent trajectory to be used capture from the result, this is taken inspiration from the opencode trajectories"""

    agent: AgentInfo
    metadata: AgentTrajectoryMetadata
    steps: List[AgentTrajectoryStep]
    full_metrics: AgentTrajectoryMetrics


class AgentResult(BaseModel):
    """This is the result which we can expect from the agent when it runs the agents"""

    status: int = Field(
        0, description="The status of the task result (0 for success, -1 for failure)"
    )
    stdout: str | None
    stderr: str | None
    trajectory: AgentTrajectory | None = Field(
        None, description="The trajectory of the agent"
    )


class AgentConfig(BaseModel):
    """The agent config to be passed to the data object"""

    name: str = Field(
        ..., description="The name of the agent to be used with the agent"
    )
    agent: str|Any = Field(..., description="The Existing Agent to be used with the agent")
    run_dir: str = Field(
        ..., description="The task context directory where the task needs to run"
    )
    backend: str = Field(..., description="The backend name for the agent to run on")
    backend_config: ContainerExecConfig | ExecConfig = Field(
        ..., description="The backend sandbox exeutor confguration to be executed"
    )
    agent_run_timeout: int = Field(3600, description="The run timeout for the agent")
    skip_setup:bool = Field(False, description="Skip the setup of the agent")
    agent_run_config:Dict[str, Any] = Field(
        {}, description="The agent run configuration which is specific to the agent")
    agent_path: str = Field(
        "/opencode", description="The path where the agent is installed"
    )

class AgentCoreConfig(BaseModel):
    """The agent core configuration to be used to initialize the agent"""

    name: str = Field(..., description="The name of the agent")
    model: Any = Field(None, description="The model configuration for the agent")
    agent_path: str = Field(
        "/opencode", description="The path where the agent is installed"
    )
    agent_run_config:Dict[str, Any] = Field(
        {}, description="The agent run configuration which is specific to the agent")
    run_timeout: int = Field(3600, description="The run timeout for the agent")
    skip_setup:bool = Field(False, description="Skip the setup of the agent")

    def get(self, key: str, default: Any = None) -> Any:
        """Helper to get configuration values"""
        return getattr(self, key, default)
