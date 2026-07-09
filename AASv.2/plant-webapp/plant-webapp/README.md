# Plant Care Web App

Migration of the original Raspberry Pi Discord bot project into a
Next.js + FastAPI web application, reusing as much of the original
Python logic as possible.

```
plant-webapp/
├── backend/          FastAPI app (routes, services, hardware, DB, scheduler)
└── frontend/          Next.js + Tailwind dashboard
```

## Quick start

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY and SECRET_KEY
uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Visit http://localhost:3000 → redirects to `/dashboard` (log in first at `/login`).

## What changed vs. the original 3-file project

| Concern | Old | New |
|---|---|---|
| Interface | Discord bot commands/buttons | REST API + Next.js dashboard |
| Storage | `tank_levels.json`, `fertilizer_log.json` | SQLAlchemy models / PostgreSQL (SQLite for dev) |
| Secrets | Hardcoded Discord token & Gemini key in source | `.env` files, loaded via `pydantic-settings` |
| Hardware code | Mixed into `main.py` and called directly from `bot.py` | Isolated in `backend/app/hardware/`, with a mock layer for non-Pi dev machines |
| Business logic | Mixed into Discord event handlers | Isolated in `backend/app/services/`, hardware-agnostic and unit-testable |
| Scheduling | `apscheduler` jobs registered inline in `bot.py` | `backend/app/scheduler/jobs.py` |
| Live updates | None (had to check Discord manually) | WebSocket (`/ws/live`) broadcasting sensor/tank/irrigation/fertilizer events |
| Auth | Discord identity | JWT login (`/api/auth/register`, `/api/auth/login`) |
| Multi-plant | Single global state | `Plant` model; every sensor reading, log, and analysis is scoped to a `plant_id` |

See `backend/README.md` for the full function-by-function mapping from the
original files to their new locations, and the code comments at the top of
each service/hardware module for what was reused verbatim vs. refactored.

## Deployment note

The FastAPI backend is meant to keep running directly on the Raspberry Pi
(set `ENABLE_GPIO=true` there) so it retains direct GPIO access to your
pumps and sensors. The Next.js frontend can run anywhere — on the Pi itself,
or on a separate machine/server — and just needs `NEXT_PUBLIC_API_URL` /
`NEXT_PUBLIC_WS_URL` pointed at the Pi's address.

## Known follow-ups (flagged, not blocking)
- `backend/app/hardware/sensors.py` has TODO stubs for soil temp / air
  temp+humidity / light sensors — the original project only ever read the
  single digital moisture pin, so these need real sensor wiring + drivers.
- `IrrigationLog`/`FertilizerLog` cooldown and history queries assume one
  DB session per request; under heavy concurrent pump usage you may want
  a lock around `tank_service.deduct` to avoid a race between two near-
  simultaneous fertilizer applications overdrawing a tank.
- Add Alembic migrations before running against a real Postgres instance
  in production (currently `init_db()` just does `create_all`, fine for
  development).
