from typing import Protocol, Any, Set, Dict, runtime_checkable
import os
import json
import logging

logger = logging.getLogger(__name__)


@runtime_checkable
class State(Protocol):
    """Protocol for state management"""

    def load(self) -> None:
        """Load the state from persistent storage"""

    def contains(self, item: Any) -> bool:
        """Check if the item is already processed"""

    def update(self, event: str, result: Any, description: Any = None) -> None:
        """
        Update the state with the result of processing an item.
        """

    def save(self) -> None:
        """Save the current state to persistent storage"""


@runtime_checkable
class JobState(Protocol):
    """This Protocol manages the state of a job, tracking processed items"""

    def load(self) -> None:
        """Load the state from persistent storage"""

    def load_metadata(self) -> None:
        """Load the metadata from persistent storage"""

    def save_metadata(self) -> None:
        """Save the metadata to persistent storage"""

    def update_metadata(self, key: str, value: Any) -> None:
        """Update the metadata"""

    def publish_summary(self, report: Dict[str, Any]):
        """Publish the summary report"""

    def contains(self, item: Any) -> bool:
        """Check if the item is already processed"""

    def update(self, result: Any, item: Any) -> None:
        """Update the state with the result of processing an item"""

    def save(self) -> None:
        """Save the current state to persistent storage"""

    def get_current_retry_level(self) -> int:
        """Get the current retry level"""
        return 1

    def increment_current_retry_level(self) -> int:
        """Increment and return the current retry level"""

    def get_task_state(self, task_id: str, sub_task_id: int | None = None) -> Any:
        """Get the state of a specific task"""


class LocalFileSystemState(State):
    """Local file system implementation of StateManager"""

    def __init__(self, root_path: str, filename: str = "state.json", key: str = "id"):
        self.file_path: str | None = os.path.join(root_path, filename)
        self.key = key
        self.processed_ids: Set[str] = set()

    def load(self) -> None:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r") as f:
                    for line in f:
                        if line.strip():
                            try:
                                self.processed_ids.add(json.loads(line.strip()))
                            except json.JSONDecodeError:
                                self.processed_ids.add(line.strip())
                logger.info(
                    f"Loaded {len(self.processed_ids)} items from {self.file_path}"
                )
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")

    def _get_id(self, item: Any) -> str:
        if isinstance(item, dict):
            return str(item.get(self.key, str(item)))
        if hasattr(item, self.key):
            return str(item.id)
        return str(item)

    def contains(self, item: Any) -> bool:
        return self._get_id(item) in self.processed_ids

    def update(self, event: str, result: Any, description: Any = None) -> None:
        item_id = None
        if hasattr(result, "metadata") and result.metadata:
            if "data" in result.metadata:
                item_id = self._get_id(result.metadata["data"])

        if item_id and item_id not in self.processed_ids:
            self.processed_ids.add(item_id)
            if self.file_path:
                try:
                    with open(self.file_path, "a") as f:
                        f.write(json.dumps(item_id) + "\n")
                except Exception as e:
                    logger.error(f"Failed to append to state file: {e}")

    def save(self) -> None:
        if self.file_path:
            try:
                with open(self.file_path, "w") as f:
                    for item in sorted(self.processed_ids):
                        f.write(json.dumps(item) + "\n")
            except Exception as e:
                logger.error(f"Failed to save state file: {e}")

