"""
Tank service — replaces the module-level `tank_levels` dict + JSON file in
main.py (load_tank_levels/save_tank_levels/initialize_tanks/reset_tank)
with DB-backed equivalents. Logic (has_enough / deduct / refill / reset)
mirrors the original checks exactly, just against Tank rows instead of a dict.
"""
from sqlalchemy.orm import Session
from app.config import settings
from app.models.tank import Tank

VALID_NUTRIENTS = ("N", "P", "K")


def ensure_tanks_exist(db: Session):
    """Called on startup — equivalent to main.py's load_tank_levels()
    falling back to DEFAULT_LEVEL when no file exists."""
    for nutrient in VALID_NUTRIENTS:
        tank = db.query(Tank).filter(Tank.nutrient == nutrient).first()
        if not tank:
            db.add(Tank(nutrient=nutrient, level_ml=settings.default_tank_level_ml))
    db.commit()


def get_status(db: Session) -> dict[str, float]:
    tanks = db.query(Tank).all()
    return {t.nutrient: t.level_ml for t in tanks}


def has_enough(db: Session, nutrient: str, amount_ml: float) -> bool:
    tank = db.query(Tank).filter(Tank.nutrient == nutrient).first()
    return bool(tank) and tank.level_ml >= amount_ml


def deduct(db: Session, nutrient: str, amount_ml: float) -> Tank | None:
    tank = db.query(Tank).filter(Tank.nutrient == nutrient).first()
    if not tank:
        return None
    tank.level_ml -= amount_ml
    db.commit()
    db.refresh(tank)
    return tank


def refill(db: Session, nutrient: str, amount_ml: float) -> Tank | None:
    """Equivalent to bot.py's !refill command."""
    nutrient = nutrient.upper()
    if nutrient not in VALID_NUTRIENTS:
        return None
    tank = db.query(Tank).filter(Tank.nutrient == nutrient).first()
    if not tank:
        tank = Tank(nutrient=nutrient, level_ml=0)
        db.add(tank)
    tank.level_ml += amount_ml
    db.commit()
    db.refresh(tank)
    return tank


def reset_tank(db: Session, nutrient: str, level_ml: float = None) -> Tank | None:
    """Equivalent to main.py's reset_tank()."""
    nutrient = nutrient.upper()
    if nutrient not in VALID_NUTRIENTS:
        return None
    level_ml = settings.default_tank_level_ml if level_ml is None else level_ml
    tank = db.query(Tank).filter(Tank.nutrient == nutrient).first()
    if not tank:
        tank = Tank(nutrient=nutrient, level_ml=level_ml)
        db.add(tank)
    else:
        tank.level_ml = level_ml
    db.commit()
    db.refresh(tank)
    return tank


def reset_all_tanks(db: Session, level_ml: float = None) -> dict[str, float]:
    """Equivalent to main.py's initialize_tanks()."""
    level_ml = settings.default_tank_level_ml if level_ml is None else level_ml
    for nutrient in VALID_NUTRIENTS:
        reset_tank(db, nutrient, level_ml)
    return get_status(db)
