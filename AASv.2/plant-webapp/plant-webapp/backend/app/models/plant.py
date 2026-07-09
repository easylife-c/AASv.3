from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Plant(Base):
    """A single tracked plant. Multi-plant support: every sensor reading,
    irrigation log, fertilizer log, and AI analysis is scoped to a plant_id."""
    __tablename__ = "plants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    species = Column(String, nullable=True)
    height_cm = Column(Float, nullable=True)
    width_cm = Column(Float, nullable=True)
    growth_stage = Column(String, default="vegetative")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sensor_readings = relationship("SensorReading", back_populates="plant")
    fertilizer_logs = relationship("FertilizerLog", back_populates="plant")
    irrigation_logs = relationship("IrrigationLog", back_populates="plant")
    analyses = relationship("PlantAnalysis", back_populates="plant")
