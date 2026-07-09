"""Start/stop irrigation endpoints. The original project only had
automatic watering (auto_water_loop) with no manual trigger — this adds
manual control on top of the reused activate_water() hardware call."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.core.security import get_current_user
from app.models.irrigation_log import IrrigationLog
from app.schemas.irrigation import IrrigationStartRequest, IrrigationLogOut
from app.services import irrigation_service
from app.websockets.manager import manager

router = APIRouter(prefix="/api/irrigation", tags=["irrigation"], dependencies=[Depends(get_current_user)])


@router.post("/start", response_model=IrrigationLogOut)
async def start_irrigation(payload: IrrigationStartRequest, db: Session = Depends(get_db)):
    log = await irrigation_service.start_irrigation(db, payload.plant_id, payload.amount_ml, trigger="manual")
    await manager.broadcast({"type": "irrigation_event", "plant_id": payload.plant_id,
                              "amount_ml": payload.amount_ml, "trigger": "manual"})
    return log


@router.post("/stop")
async def stop_irrigation():
    irrigation_service.stop_irrigation()
    await manager.broadcast({"type": "irrigation_stopped"})
    return {"detail": "Irrigation stopped", "active": irrigation_service.is_active()}


@router.get("/status")
def irrigation_status():
    return {"active": irrigation_service.is_active()}


@router.get("/history/{plant_id}", response_model=List[IrrigationLogOut])
def irrigation_history(plant_id: int, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(IrrigationLog)
        .filter(IrrigationLog.plant_id == plant_id)
        .order_by(IrrigationLog.recorded_at.desc())
        .limit(limit)
        .all()
    )
