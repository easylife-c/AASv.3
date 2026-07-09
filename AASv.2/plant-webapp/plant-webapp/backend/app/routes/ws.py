from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websockets.manager import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/live")
async def websocket_live_updates(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect incoming messages, but need to keep the
            # connection open and detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
