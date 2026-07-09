from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class SensorReading(Base):
    """Historical sensor data per plant: soil moisture, soil/air temp,
    air humidity, light intensity."""
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    soil_moisture = Column(Float, nullable=True)
    soil_temperature_c = Column(Float, nullable=True)
    air_temperature_c = Column(Float, nullable=True)
    air_humidity_pct = Column(Float, nullable=True)
    light_intensity_lux = Column(Float, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    plant = relationship("Plant", back_populates="sensor_readings")
