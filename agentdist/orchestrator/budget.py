
import asyncio
from typing import Protocol, runtime_checkable

###
# The budget to control no.of success full tasks
###

@runtime_checkable
class Budget(Protocol):
    """
    Protocol for the budget control
    """

    async def is_exhausted(self) -> bool:
        """
        Return True if the budget is exhausted.
        """

    async def record(self,success: bool) -> None:
        """
        Record that item finished (successfully or not).
        """


class LocalBudget(Budget):
    """
    This is the local budget used for the in-process orchestrator process
    """

    def __init__(self, target: int, count_mode: str = "completed"):
        self.target = target
        self.count_mode = count_mode
        self._succeeded = 0
        self._failed = 0
        self._lock = asyncio.Lock()

    @property
    def _count(self) -> int:
        if self.count_mode in ("succeeded","completed"):
            return self._succeeded
        return self._succeeded + self._failed

    async def is_exhausted(self) -> bool:
        async with self._lock:
            return self._count >= self.target

    async def record(self, success: bool):
        async with self._lock:
            if success:
                self._succeeded += 1
            else:
                self._failed += 1

    @property
    def completed_count(self) -> int:
        return self._count


class GroupBudget:
    """
    The budget used by the group of the orchestrator
    """

    def __init__(self, orchestrator):
        self._orchestrator = orchestrator

    async def is_exhausted(self) -> bool:
        return self._orchestrator._group_budget_exhausted

    async def record(self, success: bool):
        pass
