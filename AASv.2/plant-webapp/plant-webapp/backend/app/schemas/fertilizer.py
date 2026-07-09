from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional


class FertilizerApplyRequest(BaseModel):
    plant_id: int
    deficiencies: List[str]
    growth_stage: Optional[str] = "vegetative"
    # height/width default to the plant's stored dimensions if omitted
    height_cm: Optional[float] = None
    width_cm: Optional[float] = None


class FertilizerResultItem(BaseModel):
    nutrient: str
    amount_ml: float
    status: str  # applied | skipped_cooldown | tank_empty | unknown_nutrient
    detail: Optional[str] = None


class FertilizerApplyResponse(BaseModel):
    plant_id: int
    results: List[FertilizerResultItem]


class FertilizerLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    nutrient: str
    amount_ml: float
    status: str
    applied_at: datetime
