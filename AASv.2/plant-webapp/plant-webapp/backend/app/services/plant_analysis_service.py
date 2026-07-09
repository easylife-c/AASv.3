"""
AI plant analysis service — the direct descendant of plant_api.py.

Reused as-is:
  - The Gemini prompt (species/deficiencies/diseases/height/width JSON schema)
  - The response cleanup regex for stripping ```json fences
  - compute_fertilizer_amount()'s canopy-area-based grams calculation
    (kept here as `estimate_fertilizer_grams`, distinct from the mL-based
    `compute_fertilizer` in fertilizer_service.py which drives the actual
    pump timing — plant_api.py's version was always just a rough on-screen
    estimate, not what activate_pump() used)

Refactored:
  - API key now comes from settings (env var), not hardcoded in source.
  - No more building a human-readable "display" string here — that was
    Discord-message formatting. The route/frontend now render the
    structured JSON directly. This keeps the service returning pure data.
  - Takes image bytes directly instead of a saved temp file path, since the
    FastAPI upload endpoint hands us bytes from an UploadFile.
"""
import json
import re
import logging
import google.generativeai as genai

from app.config import settings

logger = logging.getLogger("plant_analysis")

genai.configure(api_key=settings.gemini_api_key)
_model = genai.GenerativeModel(settings.gemini_model)

PROMPT = (
    "You are a plant pathologist AI. Analyze the provided image to detect plant species, "
    "any visible diseases, and nutrient deficiencies.\n"
    "Only focus on deficiencies in Nitrogen, Phosphorus, and Potassium (N, P, K). "
    "For each, give a probability percentage if present.\n"
    "Return your analysis in **strict** JSON format like this:\n"
    "{\n"
    '  "species": "papaya",\n'
    '  "deficiencies": ["Nitrogen"],\n'
    '  "probabilities": {\n'
    '    "Nitrogen": "54%"\n'
    "  },\n"
    '  "diseases": ["Fungal Leaf Spot"],\n'
    '  "height": 75,\n'
    '  "width": 50,\n'
    '  "auto": true\n'
    "}\n"
    "If no deficiencies or diseases are detected, return empty lists for them.\n"
)

_BASE_FERTILIZER_RATES = {"Nitrogen": 0.6, "Phosphorus": 0.4, "Potassium": 0.5}
_FERTILIZER_PRODUCT = {"Nitrogen": "urea", "Phosphorus": "phosphate", "Potassium": "potash"}


def estimate_fertilizer_grams(deficiencies: list[str], height_cm: float, width_cm: float) -> list[dict]:
    """Rough on-screen estimate based on canopy area, from plant_api.py's
    compute_fertilizer_amount(). Kept separate from the mL dosing math in
    fertilizer_service.py, which is what actually drives the pumps."""
    canopy_area_cm2 = 3.14 * (height_cm / 2) * (width_cm / 2)
    lines = []
    for nutrient in deficiencies:
        rate = _BASE_FERTILIZER_RATES.get(nutrient, 0.5)
        amount_grams = round(canopy_area_cm2 * rate / 100, 1)
        product = _FERTILIZER_PRODUCT.get(nutrient, "fertilizer")
        lines.append({"nutrient": nutrient, "amount_grams": amount_grams, "product": product})
    return lines


def identify_plant(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Analyze a plant image using Gemini. Returns structured data:
    species, deficiencies, diseases, probabilities, height, width, auto.
    Raises ValueError on parse failure so the route can return a clean 502."""
    try:
        image_data = {"mime_type": mime_type, "data": image_bytes}
        response = _model.generate_content([PROMPT, image_data])
        text = response.text.strip()

        json_string = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
        json_string = re.sub(r"^json", "", json_string, flags=re.IGNORECASE).strip()

        result = json.loads(json_string)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini response was not valid JSON: {e}")
        raise ValueError("Could not parse AI response as JSON") from e
    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}")
        raise

    return {
        "species": result.get("species", "Unknown"),
        "deficiencies": result.get("deficiencies", []),
        "probabilities": result.get("probabilities", {}),
        "diseases": result.get("diseases", []),
        "height": result.get("height", 100),
        "width": result.get("width", 100),
        "auto": result.get("auto", False),
    }
