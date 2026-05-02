"""WebSocket broadcast manager with Redis Pub/Sub.

Each app container keeps a local dict of open WebSocket connections.
When any container (including the game scheduler) wants to broadcast an
event it publishes to a Redis Pub/Sub channel.  A background listener task
in every app container receives the message and forwards it to the local
connected clients.

This makes WebSocket broadcasts work correctly across multiple app replicas
without any shared in-process state.
"""
import asyncio
import json
import logging

from fastapi import WebSocket

from core.config import settings
from core.redis_client import get_redis

log = logging.getLogger(__name__)

CHANNEL = settings.redis_pubsub_channel


class RealtimeManager:
    def __init__(self) -> None:
        # WebSocket → role mapping (local to this process)
        self.active: dict[WebSocket, str | None] = {}
        self._listener_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket, role: str | None = None) -> None:
        await websocket.accept()
        self.active[websocket] = role

    def disconnect(self, websocket: WebSocket) -> None:
        self.active.pop(websocket, None)

    # ------------------------------------------------------------------
    # Publishing (send to all containers via Redis)
    # ------------------------------------------------------------------

    async def publish(self, event: str, data: dict, roles: set[str] | None = None) -> None:
        """Publish an event to Redis Pub/Sub so all containers receive it."""
        r = get_redis()
        message = json.dumps({"event": event, "data": data, "roles": list(roles) if roles else None})
        await r.publish(CHANNEL, message)

    # alias used by game_orchestrator for compatibility
    async def broadcast(self, event: str, data: dict, roles: set[str] | None = None) -> None:
        await self.publish(event, data, roles)

    # ------------------------------------------------------------------
    # Local delivery (called by the subscriber loop)
    # ------------------------------------------------------------------

    async def _deliver(self, event: str, data: dict, roles: set[str] | None) -> None:
        stale: list[WebSocket] = []
        for socket, role in list(self.active.items()):
            if roles is not None and role not in roles:
                continue
            try:
                await socket.send_json({"event": event, "data": data})
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)

    # ------------------------------------------------------------------
    # Background Redis subscriber
    # ------------------------------------------------------------------

    async def start_listener(self) -> None:
        """Start the Redis Pub/Sub listener. Call once at app startup."""
        if self._listener_task and not self._listener_task.done():
            return
        self._listener_task = asyncio.create_task(self._listener_loop(), name="redis-pubsub-listener")
        log.info("Redis Pub/Sub listener started on channel '%s'.", CHANNEL)

    async def stop_listener(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

    async def _listener_loop(self) -> None:
        r = get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(CHANNEL)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                    roles = set(payload["roles"]) if payload.get("roles") else None
                    await self._deliver(payload["event"], payload["data"], roles)
                except Exception as exc:
                    log.warning("Bad Pub/Sub message: %s", exc)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(CHANNEL)
            await pubsub.aclose()


manager = RealtimeManager()
