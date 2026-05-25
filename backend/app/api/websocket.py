"""Enhanced WebSocket for real-time orchestrator and project updates."""

import json
from typing import Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.orchestrator.pubsub import agent_pubsub
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class ProjectConnectionManager:
    """Manages WebSocket connections with project-specific rooms."""

    def __init__(self):
        # project_id -> set of WebSocket connections
        self.project_rooms: Dict[str, Set[WebSocket]] = {}
        # global connections (for broadcast)
        self.global_connections: Set[WebSocket] = set()
        self._pubsub_listener_added = False

    async def connect(self, websocket: WebSocket, project_id: Optional[str] = None):
        await websocket.accept()
        self.global_connections.add(websocket)
        if project_id:
            if project_id not in self.project_rooms:
                self.project_rooms[project_id] = set()
            self.project_rooms[project_id].add(websocket)

        # Start pub/sub listener on first connection
        if not self._pubsub_listener_added:
            self._pubsub_listener_added = True
            try:
                await agent_pubsub.connect()
                agent_pubsub.add_listener(self._on_pubsub_message)
            except Exception as exc:
                logger.error("websocket_pubsub_connect_error", error=str(exc))

    def disconnect(self, websocket: WebSocket, project_id: Optional[str] = None):
        self.global_connections.discard(websocket)
        if project_id and project_id in self.project_rooms:
            self.project_rooms[project_id].discard(websocket)
            if not self.project_rooms[project_id]:
                del self.project_rooms[project_id]

    async def broadcast_to_project(self, project_id: str, message: dict):
        """Send message to all connections subscribed to a project."""
        if project_id not in self.project_rooms:
            return
        disconnected = set()
        for connection in self.project_rooms[project_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        for conn in disconnected:
            self.disconnect(conn, project_id)

    async def broadcast_global(self, message: dict):
        """Send message to all connected clients."""
        disconnected = set()
        for connection in self.global_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def _on_pubsub_message(self, channel: str, payload: dict):
        """Handle messages from Redis pub/sub."""
        if channel.startswith("project:"):
            project_id = channel.replace("project:", "")
            await self.broadcast_to_project(project_id, payload)
        elif channel == "orchestrator:events":
            await self.broadcast_global(payload)
        elif channel == "agent:results":
            # Forward agent results to relevant project room
            project_id = payload.get("project_id")
            if project_id:
                await self.broadcast_to_project(project_id, {
                    "type": "agent_result",
                    "payload": payload,
                })


manager = ProjectConnectionManager()


@router.websocket("/notifications")
async def global_notifications_websocket(websocket: WebSocket):
    """Global notifications WebSocket."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # Echo with ack
                await websocket.send_json({"type": "ack", "payload": payload})
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/projects/{project_id}")
async def project_websocket(websocket: WebSocket, project_id: str):
    """Project-specific real-time updates WebSocket."""
    await manager.connect(websocket, project_id)
    try:
        await websocket.send_json({
            "type": "connected",
            "project_id": project_id,
            "message": f"Subscribed to project {project_id} updates",
        })
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                msg_type = payload.get("type")

                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": payload.get("timestamp")})
                elif msg_type == "request_state":
                    # Client requesting current orchestrator state
                    from app.orchestrator.orchestrator import KimiClawOrchestrator
                    from app.database import AsyncSessionLocal
                    async with AsyncSessionLocal() as db:
                        orch = KimiClawOrchestrator(db)
                        import uuid
                        state = await orch.get_project_state(uuid.UUID(project_id))
                        await websocket.send_json({
                            "type": "orchestrator_state",
                            "payload": state,
                        })
                else:
                    await websocket.send_json({"type": "ack", "payload": payload})
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)


@router.websocket("/review-queue")
async def review_queue_websocket(websocket: WebSocket):
    """Real-time review queue updates."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                await websocket.send_json({"type": "ack", "payload": payload})
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
