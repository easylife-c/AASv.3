"""
Scheduler module — extracted from bot.py (which called
scheduler.add_job(...) directly inline) and main.py's auto_water_loop().

Reused:
  - The auto-watering trigger condition (moisture == 0 -> dry -> water)
    from main.py's auto_water_loop, now writing to IrrigationLog + pushing
    a websocket event instead of just print().
  - The daily 8:30 AM cron pattern from bot.py's on_ready(), now used for
    a periodic sensor snapshot instead of a Discord "take a photo" reminder
    (there's no bot to click a Discord button on the web app; the
    dashboard shows an upload prompt instead — see frontend).

New:
  - A short-interval job that broadcasts sensor readings over WebSocket so
    the dashboard updates live, independent of the watering loop.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import SessionLocal
from app.hardware import sensors
from app.hardware.gpio_controller import activate_water
from app.models.sensor_reading import SensorReading
from app.models.irrigation_log import IrrigationLog
from app.websockets.manager import manager

logger = logging.getLogger("scheduler")
scheduler = AsyncIOScheduler(timezone=settings.timezone)

AUTO_WATER_ML = 50.0
DEFAULT_PLANT_ID = 1  # single-plant Pi installs default to plant #1; multi-plant
                       # setups should extend this to iterate all registered plants


async def sensor_snapshot_job():
    """Reads sensors, persists a SensorReading row, and pushes it live to
    any connected dashboard clients."""
    db = SessionLocal()
    try:
        readings = sensors.read_all_sensors()
        row = SensorReading(plant_id=DEFAULT_PLANT_ID, **readings)
        db.add(row)
        db.commit()
        db.refresh(row)

        await manager.broadcast({
            "type": "sensor_update",
            "plant_id": DEFAULT_PLANT_ID,
            "data": readings,
            "recorded_at": row.recorded_at.isoformat() if row.recorded_at else datetime.utcnow().isoformat(),
        })

        # Auto-watering: same trigger condition as the original auto_water_loop
        if readings["soil_moisture"] == 0:
            logger.info("Dry soil detected — activating water pump.")
            activate_water(AUTO_WATER_ML)
            irrigation_row = IrrigationLog(plant_id=DEFAULT_PLANT_ID, amount_ml=AUTO_WATER_ML, trigger="auto")
            db.add(irrigation_row)
            db.commit()
            await manager.broadcast({
                "type": "irrigation_event",
                "plant_id": DEFAULT_PLANT_ID,
                "amount_ml": AUTO_WATER_ML,
                "trigger": "auto",
            })
        else:
            logger.info("Soil is moist, no watering needed.")
    except Exception as e:
        logger.exception(f"sensor_snapshot_job failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """Call once on app startup. Matches the original 10-minute
    auto-watering check interval and adds a live-update cadence."""
    scheduler.add_job(sensor_snapshot_job, "interval", minutes=10, id="sensor_and_auto_water")
    scheduler.start()
    logger.info("Scheduler started: sensor snapshot + auto-water check every 10 minutes.")
