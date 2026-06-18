"""WebSocket connection manager with session-based routing."""
import json
from fastapi import WebSocket
from typing import Any


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[session_id] = websocket

    def disconnect(self, session_id: str) -> None:
        self._connections.pop(session_id, None)

    async def send(self, session_id: str, data: dict[str, Any]) -> None:
        ws = self._connections.get(session_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data, default=str))
            except Exception:
                self.disconnect(session_id)


ws_manager = ConnectionManager()
