from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class FertilizerLog(Base):
    """Replaces fertilizer_log.json. Tracks each fertilizer application
    per plant/nutrient, used for cooldown checks and history display."""
    __tablename__ = "fertilizer_logs"

    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    nutrient = Column(String, nullable=False)
    amount_ml = Column(Float, nullable=False)
    status = Column(String, default="applied")  # applied | skipped_cooldown | tank_empty
    applied_at = Column(DateTime(timezone=True), server_default=func.now())

    plant = relationship("Plant", back_populates="fertilizer_logs")
