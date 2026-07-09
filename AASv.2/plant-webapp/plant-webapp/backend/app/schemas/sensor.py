from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class SensorReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    soil_moisture: Optional[float]
    soil_temperature_c: Optional[float]
    air_temperature_c: Optional[float]
    air_humidity_pct: Optional[float]
    light_intensity_lux: Optional[float]
    recorded_at: datetime
