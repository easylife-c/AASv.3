from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PlantAnalysis(Base):
    """Stores each Gemini AI analysis result instead of only displaying
    it once in Discord and discarding it."""
    __tablename__ = "plant_analyses"

    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    species = Column(String, nullable=True)
    deficiencies = Column(JSON, default=list)
    diseases = Column(JSON, default=list)
    probabilities = Column(JSON, default=dict)
    height_cm = Column(Float, nullable=True)
    width_cm = Column(Float, nullable=True)
    auto = Column(Boolean, default=False)
    image_filename = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plant = relationship("Plant", back_populates="analyses")
