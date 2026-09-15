from typing import Protocol, List
from pathlib import Path


class ExecutionBackend(Protocol):
    """This is the ExecutionBackend protocol to be used for the sandbox like environment for execution of the agents"""

    @property
    def env_name(self):
        """The property to return the environment name"""

    async def start(self) -> None:
        """This is used to start the executor backend"""

    async def exec(self, cmd: List[str], cwd=None, timeout=None):
        """This is used to execute command and return result"""

    async def put_file(self, source_file: Path | str, target_file: Path | str):
        """This is used to copy the file to target executor"""

    async def get_file(self, source_file: Path | str, target_file: Path | str,**kwargs):
        """This is used to download the file from the executor"""

    async def stop(self):
        """This is used to stop the executor"""

    def cleanup(self):
        """This is used to cleanup the executor"""
