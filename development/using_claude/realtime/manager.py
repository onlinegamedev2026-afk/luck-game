from fastapi import WebSocket


class RealtimeManager:
    def __init__(self) -> None:
        self.active: dict[WebSocket, str | None] = {}

    async def connect(self, websocket: WebSocket, role: str | None = None) -> None:
        await websocket.accept()
        self.active[websocket] = role

    def disconnect(self, websocket: WebSocket) -> None:
        self.active.pop(websocket, None)

    async def broadcast(self, event: str, data: dict, roles: set[str] | None = None) -> None:
        stale = []
        for socket, role in list(self.active.items()):
            if roles is not None and role not in roles:
                continue
            try:
                await socket.send_json({"event": event, "data": data})
            except RuntimeError:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)


manager = RealtimeManager()
