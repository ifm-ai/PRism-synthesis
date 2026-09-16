from typing import Any, Dict, List, Tuple

from agentdist.events.eventbus import Event, EventBus
from agentdist.observability.logging import Logger
from agentdist.constants import _DEFAULT_EVENT_BUS_PORT

logger = Logger.get_logger(__name__)



class EventBusServer:
    """
    Thin aiohttp.web wrapper around one EventBus.
    """

    def __init__(self, bus: EventBus, host: str = "0.0.0.0", port: int = _DEFAULT_EVENT_BUS_PORT):
        self._bus = bus
        self._host = host
        self._port = port
        self._runner = None

    @property
    def port(self) -> int:
        return self._port

    async def start(self) -> None:
        if self._runner is not None:
            return
        from aiohttp import web

        app = web.Application()
        app.router.add_get("/health", self._handle_health)
        app.router.add_get("/events", self._handle_get_events)
        app.router.add_post("/events", self._handle_post_event)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        if self._runner.addresses:
            self._port = self._runner.addresses[0][1]
        logger.debug(f"Event bus HTTP server listening on {self._host}:{self._port}")

    async def stop(self) -> None:
        if self._runner is None:
            return
        await self._runner.cleanup()
        self._runner = None

    async def _handle_health(self, request):
        from aiohttp import web

        return web.json_response({"status": "ok"})

    async def _handle_get_events(self, request):
        from aiohttp import web

        try:
            since = int(request.query.get("since", "0"))
        except ValueError:
            return web.json_response({"error": "invalid 'since' query param"}, status=400)
        events = self._bus.events_since(since)
        return web.json_response(
            {
                "events": [e.to_dict() for e in events],
                "latest_seq": self._bus.latest_seq,
            }
        )

    async def _handle_post_event(self, request):
        from aiohttp import web
        try:
            data = await request.json()
            category = data["category"]
        except Exception as e:
            return web.json_response({"error": f"invalid event payload: {e}"}, status=400)
        payload = data.get("payload") or {}
        await self._bus.pub(category, payload)
        return web.json_response({"status": "ok"})


class EventBusClient:
    """Used by the Master to fetch/push events
    """

    def __init__(self, timeout_sec=5):
        self._timeout_sec = timeout_sec

    async def fetch_events(
        self, host: str, port: int, since: int = 0
    ) -> Tuple[List[Event], int]:
        import aiohttp

        url = f"http://{host}:{port}/events"
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._timeout_sec)
        ) as session:
            async with session.get(url, params={"since": str(since)}) as resp:
                resp.raise_for_status()
                data = await resp.json()
        events = [Event.from_dict(e) for e in data.get("events", [])]
        latest_seq = data.get("latest_seq", since)
        return events, latest_seq

    async def push_event(
        self, host: str, port: int, category: str, payload: Dict[str, Any]
    ) -> None:
        import aiohttp

        url = f"http://{host}:{port}/events"
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._timeout_sec)
        ) as session:
            async with session.post(
                url, json={"category": category, "payload": payload}
            ) as resp:
                resp.raise_for_status()
