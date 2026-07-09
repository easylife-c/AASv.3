"""Replaces bot.py's !submit / !applyfertilizer / ConfirmApplyView /
GrowthStageView flow with a single POST endpoint. The frontend collects
deficiencies + growth stage (equivalent to what those Discord buttons did)
and calls this once."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.core.security import get_current_user
from app.models.plant import Plant
from app.models.fertilizer_log import FertilizerLog
from app.schemas.fertilizer import FertilizerApplyRequest, FertilizerApplyResponse, FertilizerLogOut
from app.services import fertilizer_service
from app.websockets.manager import manager

router = APIRouter(prefix="/api/fertilizer", tags=["fertilizer"], dependencies=[Depends(get_current_user)])


@router.post("/apply", response_model=FertilizerApplyResponse)
async def apply_fertilizer(payload: FertilizerApplyRequest, db: Session = Depends(get_db)):
    plant = db.query(Plant).filter(Plant.id == payload.plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    height = payload.height_cm or plant.height_cm
    width = payload.width_cm or plant.width_cm
    if not height or not width:
        raise HTTPException(status_code=400, detail="Plant height/width required (not set on plant or in request)")

    results = await fertilizer_service.apply_fertilizer(
        db, plant.id, height, width, payload.deficiencies,
        payload.growth_stage or plant.growth_stage,
    )

    await manager.broadcast({"type": "fertilizer_event", "plant_id": plant.id, "results": results})
    return FertilizerApplyResponse(plant_id=plant.id, results=results)


@router.get("/history/{plant_id}", response_model=List[FertilizerLogOut])
def fertilizer_history(plant_id: int, db: Session = Depends(get_db)):
    return (
        db.query(FertilizerLog)
        .filter(FertilizerLog.plant_id == plant_id)
        .order_by(FertilizerLog.applied_at.desc())
        .all()
    )
