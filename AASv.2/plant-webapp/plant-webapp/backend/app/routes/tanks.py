"""Replaces bot.py's !tank / !tanks / !refill / !init_tanks / !reset_tank_cmd
commands with REST equivalents."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.core.security import get_current_user
from app.schemas.tank import TankOut, TankRefillRequest, TankResetRequest
from app.services import tank_service
from app.websockets.manager import manager

router = APIRouter(prefix="/api/tanks", tags=["tanks"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=List[TankOut])
def get_tanks(db: Session = Depends(get_db)):
    """Equivalent to !tanks / !tank."""
    from app.models.tank import Tank
    return db.query(Tank).all()


@router.post("/refill", response_model=TankOut)
async def refill_tank(payload: TankRefillRequest, db: Session = Depends(get_db)):
    """Equivalent to !refill <nutrient> <amount>."""
    tank = tank_service.refill(db, payload.nutrient, payload.amount_ml)
    if not tank:
        raise HTTPException(status_code=400, detail=f"Invalid nutrient: {payload.nutrient}")
    await manager.broadcast({"type": "tank_update", "nutrient": tank.nutrient, "level_ml": tank.level_ml})
    return tank


@router.post("/reset", response_model=TankOut)
async def reset_single_tank(payload: TankResetRequest, db: Session = Depends(get_db)):
    """Equivalent to !reset_tank_cmd <nutrient> [level]."""
    tank = tank_service.reset_tank(db, payload.nutrient, payload.level_ml)
    if not tank:
        raise HTTPException(status_code=400, detail=f"Invalid nutrient: {payload.nutrient}")
    await manager.broadcast({"type": "tank_update", "nutrient": tank.nutrient, "level_ml": tank.level_ml})
    return tank


@router.post("/reset-all", response_model=List[TankOut])
async def reset_all_tanks(level_ml: float = 1000.0, db: Session = Depends(get_db)):
    """Equivalent to !init_tanks [level]."""
    from app.models.tank import Tank
    tank_service.reset_all_tanks(db, level_ml)
    tanks = db.query(Tank).all()
    await manager.broadcast({"type": "tanks_reset", "level_ml": level_ml})
    return tanks
