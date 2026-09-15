import inspect
import itertools
from collections import defaultdict, deque
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Callable

from agentdist.observability.logging import Logger

logger = Logger.get_logger(__name__)

class Event(BaseModel):
    seq: int = Field(description="The sequence number of the event")
    category: str = Field(description="The category of the event")
    payload: Dict[str, Any] = Field(default_factory=dict,description="The payload to be sent across the event bus")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(), description= "The timestamp of the event occured"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "category": self.category,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        return cls(
            seq=int(data["seq"]),
            category=data["category"],
            payload=data.get("payload") or {},
            timestamp=data.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        )


class EventBus:
    """
    A event bus to be communicated across the systems, where created per orchestrator
    """

    def __init__(self, max_buffer: int = 5000):
        self._seq_counter = itertools.count(1)
        self._buffer = deque(maxlen=max_buffer)
        self._subscribers = defaultdict(list)

    async def pub(self, category: str, payload: Dict[str, Any]) -> Event:
        event = Event(
            seq=next(self._seq_counter), category=category, payload=dict(payload)
        )
        self._buffer.append(event)
        handlers = list(self._subscribers.get(category, ())) + list(
            self._subscribers.get("*", ())
        )
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception as e:
                logger.warning(f"Event bus subscriber for {category!r} failed: {e}")
        return event

    def subscribe(self, category: str, handler: Callable[[Event],None]):
        """SubScribe at category """
        self._subscribers[category].append(handler)

    def events_since(self, cursor: int) -> List[Event]:
        """Just used for the event server"""
        return [e for e in self._buffer if e.seq > cursor]

    @property
    def latest_seq(self) -> int:
        return self._buffer[-1].seq if self._buffer else 0
