from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class IrrigationStartRequest(BaseModel):
    plant_id: int
    amount_ml: float = Field(default=50.0, gt=0)


class IrrigationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    amount_ml: float
    trigger: str
    recorded_at: datetime
