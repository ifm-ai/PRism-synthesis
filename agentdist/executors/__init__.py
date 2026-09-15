from agentdist.executors.docker import DockerExecutionBackend
from agentdist.executors.local import LocalExecutionBackend
from agentdist.executors.apptainer import ApptainerExecutionBackend
from agentdist.executors.protocol import ExecutionBackend
from agentdist.exceptions import EnvironmentError


class ExecutorFactory:
    """This class is just a factory to get the available executor with the provided executor name"""

    @staticmethod
    def get_executor(backend: str) -> ExecutionBackend:
        """Just a factory method to the provided backend name"""
        if backend == "docker":
            return DockerExecutionBackend
        elif backend == "local":
            return LocalExecutionBackend
        elif backend == "apptainer":
            return ApptainerExecutionBackend
        else:
            raise EnvironmentError(
                f"Provided backend {backend} execution doesn't supported"
            )
