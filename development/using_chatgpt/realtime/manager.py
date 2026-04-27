from fastapi import WebSocket


class RealtimeManager:
    def __init__(self) -> None:
        self.active: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active.discard(websocket)

    async def broadcast(self, event: str, data: dict) -> None:
        stale = []
        for socket in self.active:
            try:
                await socket.send_json({"event": event, "data": data})
            except RuntimeError:
                stale.append(socket)
        for socket in stale:
            self.disconnect(socket)


manager = RealtimeManager()

