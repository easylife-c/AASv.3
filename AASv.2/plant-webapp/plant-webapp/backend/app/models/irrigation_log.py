from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class IrrigationLog(Base):
    """Replaces the print()-only auto_water_loop history."""
    __tablename__ = "irrigation_logs"

    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    amount_ml = Column(Float, nullable=False)
    trigger = Column(String, default="auto")  # auto | manual
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    plant = relationship("Plant", back_populates="irrigation_logs")
