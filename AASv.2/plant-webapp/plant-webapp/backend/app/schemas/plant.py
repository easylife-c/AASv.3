from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class PlantCreate(BaseModel):
    name: str
    species: Optional[str] = None
    height_cm: Optional[float] = None
    width_cm: Optional[float] = None
    growth_stage: str = "vegetative"


class PlantUpdate(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    height_cm: Optional[float] = None
    width_cm: Optional[float] = None
    growth_stage: Optional[str] = None


class PlantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    species: Optional[str]
    height_cm: Optional[float]
    width_cm: Optional[float]
    growth_stage: str
    created_at: datetime
