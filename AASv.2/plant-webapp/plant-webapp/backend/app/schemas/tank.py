from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class TankOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nutrient: str
    level_ml: float
    updated_at: datetime


class TankRefillRequest(BaseModel):
    nutrient: str
    amount_ml: float = Field(gt=0)


class TankResetRequest(BaseModel):
    nutrient: str
    level_ml: float = Field(default=1000.0, ge=0)
