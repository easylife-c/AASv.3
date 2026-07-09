"""
FastAPI application entrypoint. Replaces bot.py's role as the "interface"
layer — instead of registering Discord commands/events, we mount REST
routers and a WebSocket endpoint. Startup tasks (tank initialization,
scheduler, DB table creation) replace bot.py's on_ready() handler.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.core.logging_config import configure_logging
from app.database import init_db, SessionLocal
from app.services import tank_service
from app.scheduler.jobs import start_scheduler, scheduler

from app.routes import auth, plants, analysis, fertilizer, tanks, sensors, irrigation, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()

    db = SessionLocal()
    try:
        tank_service.ensure_tanks_exist(db)  # equivalent to load_tank_levels() default fallback
    finally:
        db.close()

    start_scheduler()  # equivalent to bot.py's on_ready() scheduler.add_job(...) + auto_water_loop task
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Plant Care API",
    description="Smart agriculture backend: AI plant analysis, fertigation, irrigation, and sensor monitoring.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(plants.router)
app.include_router(analysis.router)
app.include_router(fertilizer.router)
app.include_router(tanks.router)
app.include_router(sensors.router)
app.include_router(irrigation.router)
app.include_router(ws.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
