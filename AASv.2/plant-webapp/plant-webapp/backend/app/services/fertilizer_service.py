"""
Fertilizer service — combines main.py's compute_fertilizer() (reused
verbatim, unit-for-unit) with the application/cooldown logic that used to
live inside bot.py's apply_fertilizer_logic().

Reused as-is:
  - compute_fertilizer(): identical area/multiplier/base_rate math, capped
    at 500ml per nutrient exactly like the original.
  - NUTRIENT_MAP normalization (Nitrogen/N -> N, etc).
  - The cooldown-check pattern from apply_fertilizer_logic.

Refactored:
  - fertilizer_log.json -> FertilizerLog DB rows, queried per (plant, nutrient).
  - tank_levels.json -> delegated to tank_service (DB-backed).
  - No Discord message building. Returns a list of structured results;
    the route/frontend decide how to display them.
  - activate_pump() call now runs via asyncio.to_thread since it blocks on
    time.sleep() for the pump duration, keeping the FastAPI event loop free.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.config import settings
from app.hardware.gpio_controller import activate_pump
from app.models.fertilizer_log import FertilizerLog
from app.services import tank_service

logger = logging.getLogger("fertilizer_service")

NUTRIENT_MAP = {
    "NITROGEN": "N", "PHOSPHORUS": "P", "POTASSIUM": "K",
    "N": "N", "P": "P", "K": "K",
}

STAGE_MULTIPLIERS = {"seedling": 0.5, "vegetative": 1.0, "flowering": 0.8, "fruiting": 1.2}
BASE_RATES_ML_PER_M2 = {"N": 12, "P": 8, "K": 10}


def compute_fertilizer(height_cm: float, width_cm: float, deficiencies: list[str],
                        growth_stage: str = "vegetative") -> list[dict]:
    """Identical logic to main.py's compute_fertilizer(). height/width are
    still expected in cm (divided by 50 to approximate meters, matching the
    original's unit convention)."""
    try:
        height_m = float(height_cm) / 50
        width_m = float(width_cm) / 50
    except (TypeError, ValueError):
        logger.error("Height/Width must be numeric.")
        return []

    area = height_m * width_m
    multiplier = STAGE_MULTIPLIERS.get(growth_stage.lower(), 1.0)

    results = []
    for d in deficiencies:
        d_upper = d.upper()
        nutrient = NUTRIENT_MAP.get(d_upper)
        if not nutrient:
            results.append({"nutrient": d_upper, "amount_ml": 0.0, "unknown": True})
            continue
        rate = BASE_RATES_ML_PER_M2.get(nutrient, 10)
        amount_ml = min(area * rate * multiplier, 500)  # same overdose cap as original
        results.append({"nutrient": nutrient, "amount_ml": round(amount_ml, 2), "unknown": False})
    return results


async def apply_fertilizer(db: Session, plant_id: int, height_cm: float, width_cm: float,
                            deficiencies: list[str], growth_stage: str = "vegetative") -> list[dict]:
    """Refactored version of bot.py's apply_fertilizer_logic(), stripped of
    all Discord I/O. Checks cooldown, activates pumps, deducts tanks, and
    writes a FertilizerLog row per nutrient."""
    computed = compute_fertilizer(height_cm, width_cm, deficiencies, growth_stage)
    cooldown = timedelta(hours=settings.fertilizer_cooldown_hours)
    now = datetime.now(timezone.utc)

    output = []
    for item in computed:
        nutrient = item["nutrient"]

        if item.get("unknown"):
            output.append({"nutrient": nutrient, "amount_ml": 0.0, "status": "unknown_nutrient"})
            continue

        last_log = (
            db.query(FertilizerLog)
            .filter(FertilizerLog.plant_id == plant_id, FertilizerLog.nutrient == nutrient)
            .order_by(FertilizerLog.applied_at.desc())
            .first()
        )
        if last_log and last_log.applied_at:
            applied_at = last_log.applied_at
            if applied_at.tzinfo is None:
                applied_at = applied_at.replace(tzinfo=timezone.utc)
            if now - applied_at < cooldown:
                hours_left = round((cooldown - (now - applied_at)).total_seconds() / 3600, 1)
                output.append({
                    "nutrient": nutrient, "amount_ml": 0.0, "status": "skipped_cooldown",
                    "detail": f"Try again in {hours_left}h",
                })
                continue

        amount_ml = item["amount_ml"]
        if not tank_service.has_enough(db, nutrient, amount_ml):
            output.append({"nutrient": nutrient, "amount_ml": amount_ml, "status": "tank_empty"})
            continue

        success = await asyncio.to_thread(activate_pump, nutrient, amount_ml)
        if success:
            tank_service.deduct(db, nutrient, amount_ml)
            db.add(FertilizerLog(plant_id=plant_id, nutrient=nutrient, amount_ml=amount_ml, status="applied"))
            db.commit()
            output.append({"nutrient": nutrient, "amount_ml": amount_ml, "status": "applied"})
        else:
            output.append({"nutrient": nutrient, "amount_ml": amount_ml, "status": "pump_error"})

    return output
