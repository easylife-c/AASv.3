"""The ONE dosing engine.

v1 had two conflicting calculators (mL of solution in main.py, grams of dry
product in plant_api.py) with undocumented conversions. This module is the
single source of truth: liquid nutrient solution in mL, every constant named
and explained. The web backend imports these same rules for previews, so what
the UI predicts is exactly what the pump delivers.

Model: dose scales with canopy area. The canopy is treated as an ellipse whose
axes are the measured plant width and height projections:
    area_m2 = pi * (width_m / 2) * (height_m / 2)
Dose = area_m2 * base_rate_ml_per_m2[nutrient] * stage_multiplier, clamped.
Agronomic note: base rates are starting values for dilute liquid feed on young
trees — tune them against your fertilizer label and your advisor's guidance.
"""

from __future__ import annotations

import math
from pydantic import BaseModel, Field

# mL of nutrient solution per m² of canopy, per application (vegetative stage)
BASE_RATE_ML_PER_M2 = {"N": 12.0, "P": 8.0, "K": 10.0}

# Growth-stage multipliers (agronomy: heavy N early, K-shift for fruiting)
STAGE_MULTIPLIER = {
    "seedling": 0.5,
    "vegetative": 1.0,
    "flowering": 0.8,
    "fruiting": 1.2,
}

CM_PER_M = 100.0


class PlantMeasure(BaseModel):
    """Validated plant measurements. Rejects nonsense (including anything an
    LLM might hallucinate) before it can reach dose math."""
    species: str = "unknown"
    height_cm: float = Field(ge=5, le=2000)   # 5 cm seedling .. 20 m tree
    width_cm: float = Field(ge=5, le=2000)
    growth_stage: str = "vegetative"


class Dose(BaseModel):
    nutrient: str
    amount_ml: float


def compute_doses(plant: PlantMeasure, deficiencies: list[str],
                  max_dose_ml: float = 500.0) -> list[Dose]:
    stage = plant.growth_stage.lower()
    multiplier = STAGE_MULTIPLIER.get(stage, 1.0)

    height_m = plant.height_cm / CM_PER_M
    width_m = plant.width_cm / CM_PER_M
    area_m2 = math.pi * (width_m / 2.0) * (height_m / 2.0)

    doses: list[Dose] = []
    seen: set[str] = set()
    for raw in deficiencies:
        nutrient = _normalize(raw)
        if nutrient is None or nutrient in seen:
            continue
        seen.add(nutrient)
        amount = area_m2 * BASE_RATE_ML_PER_M2[nutrient] * multiplier
        amount = min(round(amount, 1), max_dose_ml)
        if amount > 0:
            doses.append(Dose(nutrient=nutrient, amount_ml=amount))
    return doses


def _normalize(name: str) -> str | None:
    aliases = {
        "N": "N", "NITROGEN": "N",
        "P": "P", "PHOSPHORUS": "P", "PHOSPHOROUS": "P",
        "K": "K", "POTASSIUM": "K",
    }
    return aliases.get(name.strip().upper())
