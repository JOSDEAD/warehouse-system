import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# Global set of active WebSocket connections
_connected_clients: Set[WebSocket] = set()


async def broadcast(message: dict) -> None:
    """
    Send a JSON message to all currently connected WebSocket clients.
    Disconnected clients are silently removed from the pool.
    """
    if not _connected_clients:
        return

    payload = json.dumps(message)
    dead: Set[WebSocket] = set()

    for ws in list(_connected_clients):
        try:
            await ws.send_text(payload)
        except Exception as exc:
            logger.warning("Failed to send to WebSocket client — removing: %s", exc)
            dead.add(ws)

    _connected_clients.difference_update(dead)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint.  Clients (e.g. the audio daemon) connect here and
    receive real-time JSON messages pushed by the server.
    """
    await websocket.accept()
    _connected_clients.add(websocket)
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info("WebSocket client connected: %s (total: %d)", client_host, len(_connected_clients))

    try:
        # Keep the connection alive; the server is the one that pushes messages.
        while True:
            # We still receive to detect disconnection / ping frames.
            data = await websocket.receive_text()
            # Optionally handle ping/pong or client-sent messages here.
            logger.debug("WebSocket message received from %s: %s", client_host, data)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: %s", client_host)
    except Exception as exc:
        logger.warning("WebSocket error for %s: %s", client_host, exc)
    finally:
        _connected_clients.discard(websocket)
        logger.info(
            "WebSocket client removed: %s (remaining: %d)",
            client_host,
            len(_connected_clients),
        )
