"""
Irrigation service — wraps main.py's activate_water(), now logging each
event to the DB instead of only printing, and scoped per-plant.
"""
import asyncio
import logging
from sqlalchemy.orm import Session

from app.hardware.gpio_controller import activate_water
from app.models.irrigation_log import IrrigationLog

logger = logging.getLogger("irrigation_service")

# Simple in-memory flag so a "stop irrigation" endpoint has something to act
# on. The original code had no concept of manually stopping irrigation
# mid-cycle (activate_water() ran to completion via time.sleep()); this
# flag lets a future async/interruptible pump driver check it between ticks.
_irrigation_active = {"status": False}


def is_active() -> bool:
    return _irrigation_active["status"]


async def start_irrigation(db: Session, plant_id: int, amount_ml: float, trigger: str = "manual") -> IrrigationLog:
    _irrigation_active["status"] = True
    try:
        await asyncio.to_thread(activate_water, amount_ml)
    finally:
        _irrigation_active["status"] = False

    log = IrrigationLog(plant_id=plant_id, amount_ml=amount_ml, trigger=trigger)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def stop_irrigation():
    """Signals any in-progress irrigation loop to stop at its next check.
    Note: activate_water()'s blocking time.sleep() (from the original
    main.py) can't be interrupted mid-pump without switching to a
    non-blocking pump driver — flagged here as a known limitation carried
    over from the original hardware code."""
    _irrigation_active["status"] = False
