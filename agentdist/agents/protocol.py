from typing import Protocol, runtime_checkable
from agentdist.executors import ExecutionBackend
from agentdist.structures.agent import AgentContext, AgentConfig

@runtime_checkable
class Agent(Protocol):
    """This is the agent protocol to be used for execution in a environment provided"""

    def __init__(self, exec: ExecutionBackend, agent_config: AgentConfig) -> None:
        """Initialization class for the agent"""

    async def setup(self):
        """Setup of the agent to be run"""

    async def run(self, instruction: str, context: AgentContext):
        """To be used to spin up the agent"""
