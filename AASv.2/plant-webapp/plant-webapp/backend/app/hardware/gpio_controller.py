"""
Hardware control module — the direct descendant of the original main.py.

Reused as-is from main.py:
  - activate_pump() / activate_water(): identical pump timing math
    (amount_ml / PUMP_RATE_ML_PER_SEC), just no more time.sleep() blocking
    the whole process — see note below.
  - read_moisture(): identical digital read logic.

Refactored:
  - Tank level get/set is delegated to app.services.tank_service (DB-backed)
    instead of module-level globals + JSON file.
  - GPIO pin setup only happens when settings.enable_gpio is True, so the
    API can run on a dev laptop without gpiozero raising errors. When
    disabled, a MockPump/MockSensor stands in and just logs actions.
  - time.sleep() (blocking) is unchanged here since pump durations are
    short (~seconds) and this runs in a threadpool via FastAPI's
    run_in_threadpool when called from async routes/services.
"""
import time
import logging
from app.config import settings

logger = logging.getLogger("hardware")


class MockOutputDevice:
    def __init__(self, pin, **kwargs):
        self.pin = pin

    def on(self):
        logger.info(f"[MOCK] Pin {self.pin} ON")

    def off(self):
        logger.info(f"[MOCK] Pin {self.pin} OFF")


class MockInputDevice:
    def __init__(self, pin, **kwargs):
        self.pin = pin
        self.value = 1  # pretend "wet" by default in dev

    def close(self):
        pass


if settings.enable_gpio:
    from gpiozero import OutputDevice, InputDevice
else:
    OutputDevice = MockOutputDevice
    InputDevice = MockInputDevice
    logger.warning("ENABLE_GPIO=false — using mock hardware layer (dev mode).")

moisture_sensor = InputDevice(settings.moisture_pin)
water_pump = OutputDevice(settings.water_pump_pin, active_high=False, initial_value=False) \
    if settings.enable_gpio else OutputDevice(settings.water_pump_pin)

pumps = {
    nutrient: (
        OutputDevice(pin, active_high=False, initial_value=False)
        if settings.enable_gpio else OutputDevice(pin)
    )
    for nutrient, pin in settings.pump_pins.items()
}


def read_moisture() -> int:
    """Reads digital moisture sensor. Returns 0 = dry, 1 = wet."""
    value = int(moisture_sensor.value)
    logger.info("Soil is DRY" if value == 0 else "Soil is WET")
    return value


def activate_water(amount_ml: float) -> float:
    """Activate the water-only pump for irrigation. Returns duration (sec)."""
    duration = amount_ml / settings.pump_rate_ml_per_sec
    logger.info(f"[WATER] Pumping {amount_ml:.1f} mL for {duration:.2f} sec")
    water_pump.on()
    time.sleep(duration)
    water_pump.off()
    return duration


def activate_pump(nutrient: str, amount_ml: float) -> bool:
    """Activates a nutrient pump for the computed duration. Does NOT check
    or mutate tank levels — that's the caller's (service layer's)
    responsibility, since tank levels now live in the DB, not in this
    hardware-only module."""
    if nutrient not in pumps:
        logger.error(f"Invalid nutrient: {nutrient}")
        return False

    duration = amount_ml / settings.pump_rate_ml_per_sec
    logger.info(f"Pumping {amount_ml:.1f} mL of {nutrient} for {duration:.2f} sec")
    pumps[nutrient].on()
    time.sleep(duration)
    pumps[nutrient].off()
    return True
