from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Tank(Base):
    """Replaces tank_levels.json. One row per nutrient tank (N/P/K)."""
    __tablename__ = "tanks"

    id = Column(Integer, primary_key=True, index=True)
    nutrient = Column(String, unique=True, index=True, nullable=False)
    level_ml = Column(Float, nullable=False, default=1000.0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
