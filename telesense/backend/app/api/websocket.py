"""
TeleSense WebSocket Manager
Provides real-time pub/sub push to web clients (NOC dashboard, mobile apps).
Broadcasts:
- Live 10-minute / tick telemetry updates
- Proactive congestion & outage alerts
- Overall network health counter updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import logging

logger = logging.getLogger("telesense.websocket")
router = APIRouter(tags=["WebSocket"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts a JSON message to all connected clients."""
        if not self.active_connections:
            return
            
        payload = json.dumps(message, default=str)
        dead_connections = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending to WebSocket client: {e}")
                dead_connections.append(connection)
                
        for dead in dead_connections:
            self.disconnect(dead)

# Global singleton
ws_manager = ConnectionManager()

@router.websocket("/ws/live")
async def websocket_live_telemetry(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Welcome message
        await websocket.send_text(json.dumps({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Connected to TeleSense Real-Time Telecom Telemetry Stream"
        }))
        
        while True:
            # Keep connection open and receive optional client messages (like ping)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket unexpected error: {e}")
        ws_manager.disconnect(websocket)

