# Plant Care Backend (FastAPI)

## Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # then fill in GEMINI_API_KEY, SECRET_KEY, etc.
```

On the Raspberry Pi, set `ENABLE_GPIO=true` in `.env`. On a dev machine
without GPIO hardware, leave it `false` — a mock hardware layer takes over
so the API still runs and returns sensible fake data.

## Run
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs: http://localhost:8000/docs

## First-time use
1. `POST /api/auth/register` to create a user.
2. `POST /api/auth/login` (OAuth2 form: username/password) to get a bearer token.
3. Use the token as `Authorization: Bearer <token>` for all other endpoints.
4. `POST /api/plants` to register your first plant.
5. `POST /api/analysis/{plant_id}/analyze` with an image file to run AI analysis.
6. `POST /api/fertilizer/apply` to compute + apply fertilizer for a plant.

## Module map (vs. the original three files)
| Old file | New location |
|---|---|
| `plant_api.py` Gemini logic | `app/services/plant_analysis_service.py` |
| `main.py` GPIO/pump code | `app/hardware/gpio_controller.py` |
| `main.py` `compute_fertilizer` | `app/services/fertilizer_service.py` |
| `main.py` tank JSON storage | `app/services/tank_service.py` + `app/models/tank.py` |
| `main.py` `auto_water_loop` | `app/scheduler/jobs.py` |
| `bot.py` `apply_fertilizer_logic` | `app/services/fertilizer_service.apply_fertilizer` |
| `bot.py` Discord commands | `app/routes/*.py` REST endpoints |
| `bot.py` reminders/scheduling | `app/scheduler/jobs.py` |
| (none — new) | `app/core/security.py`, `app/services/auth_service.py` (login) |
| (none — new) | `app/websockets/manager.py` (live dashboard updates) |
