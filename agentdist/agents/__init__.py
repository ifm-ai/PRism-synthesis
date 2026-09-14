from agentdist.agents.opencode import OpenCodeAgent
from agentdist.agents.protocol import Agent


class AgentFactory:
    """This class is just a factory to get the provided agent class"""

    @staticmethod
    def get_agent(agent: str | Agent) -> Agent:
        """Just a factory method to the provided backend name"""
        if agent == "opencode":
            return OpenCodeAgent
        elif issubclass(agent, Agent):
            return agent
        else:
            raise EnvironmentError(f"Provided agent {agent} doesn't supported")
