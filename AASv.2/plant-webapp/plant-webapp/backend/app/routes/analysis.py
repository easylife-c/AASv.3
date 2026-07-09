"""
Replaces bot.py's on_message() image-attachment handler
(save temp file -> identify_plant -> post result -> GrowthStageView).
Here: upload -> identify_plant -> persist PlantAnalysis -> return JSON.
Growth stage selection becomes a normal PATCH to /api/plants/{id} from the
frontend, then the client calls /api/fertilizer/apply — no more
button-driven multi-step Discord flow needed.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.core.security import get_current_user
from app.models.plant import Plant
from app.models.plant_analysis import PlantAnalysis
from app.schemas.analysis import PlantAnalysisOut
from app.services import plant_analysis_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"], dependencies=[Depends(get_current_user)])


@router.post("/{plant_id}/analyze", response_model=PlantAnalysisOut)
async def analyze_plant_image(plant_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    image_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    try:
        result = plant_analysis_service.identify_plant(image_bytes, mime_type)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    analysis = PlantAnalysis(
        plant_id=plant_id,
        species=result["species"],
        deficiencies=result["deficiencies"],
        diseases=result["diseases"],
        probabilities=result["probabilities"],
        height_cm=result["height"],
        width_cm=result["width"],
        auto=result["auto"],
        image_filename=file.filename,
    )
    db.add(analysis)

    # Keep the plant's latest known species/size in sync, same info the
    # original bot passed forward into apply_fertilizer_logic's `data` dict.
    plant.species = result["species"] or plant.species
    plant.height_cm = result["height"] or plant.height_cm
    plant.width_cm = result["width"] or plant.width_cm

    db.commit()
    db.refresh(analysis)
    return analysis


@router.get("/{plant_id}/history", response_model=List[PlantAnalysisOut])
def analysis_history(plant_id: int, db: Session = Depends(get_db)):
    return (
        db.query(PlantAnalysis)
        .filter(PlantAnalysis.plant_id == plant_id)
        .order_by(PlantAnalysis.created_at.desc())
        .all()
    )
