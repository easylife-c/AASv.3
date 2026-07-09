"""New REST endpoints for sensor data — the original project only ever
read sensors internally inside auto_water_loop(); there was no way to
query them on demand. This exposes both a live read and history."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.core.security import get_current_user
from app.hardware import sensors
from app.models.sensor_reading import SensorReading
from app.schemas.sensor import SensorReadingOut

router = APIRouter(prefix="/api/sensors", tags=["sensors"], dependencies=[Depends(get_current_user)])


@router.get("/live")
def read_live_sensors():
    """Equivalent to what auto_water_loop() read internally, now exposed
    as an on-demand endpoint."""
    return sensors.read_all_sensors()


@router.get("/history/{plant_id}", response_model=List[SensorReadingOut])
def sensor_history(plant_id: int, limit: int = 100, db: Session = Depends(get_db)):
    return (
        db.query(SensorReading)
        .filter(SensorReading.plant_id == plant_id)
        .order_by(SensorReading.recorded_at.desc())
        .limit(limit)
        .all()
    )
