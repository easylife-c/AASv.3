from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Dict, Optional


class PlantAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    species: Optional[str]
    deficiencies: List[str]
    diseases: List[str]
    probabilities: Dict[str, str]
    height_cm: Optional[float]
    width_cm: Optional[float]
    auto: bool
    created_at: datetime
