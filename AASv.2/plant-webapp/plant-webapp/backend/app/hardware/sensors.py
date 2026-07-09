"""
Environmental sensors beyond the original digital soil moisture switch.

The original main.py only read a single digital moisture pin. The dashboard
spec calls for soil temperature, air temperature, air humidity, and light
intensity too. This module is new — wire up your actual sensors here
(e.g. DHT22 for air temp/humidity, DS18B20 for soil temp, a BH1750 or LDR
for light). Until then it returns None so the API/dashboard degrade
gracefully instead of crashing.
"""
import logging
from typing import Optional
from app.hardware.gpio_controller import read_moisture
from app.config import settings

logger = logging.getLogger("sensors")


def read_all_sensors() -> dict:
    """Aggregate reading used by the /sensors endpoint and the scheduler's
    periodic broadcast. Extend each read_* function as real sensors are
    wired in."""
    return {
        "soil_moisture": float(read_moisture()),
        "soil_temperature_c": read_soil_temperature(),
        "air_temperature_c": read_air_temperature(),
        "air_humidity_pct": read_air_humidity(),
        "light_intensity_lux": read_light_intensity(),
    }


def read_soil_temperature() -> Optional[float]:
    # TODO: wire up a DS18B20 or similar. Placeholder for now.
    if not settings.enable_gpio:
        return None
    return None


def read_air_temperature() -> Optional[float]:
    # TODO: wire up a DHT22 or similar.
    if not settings.enable_gpio:
        return None
    return None


def read_air_humidity() -> Optional[float]:
    # TODO: wire up a DHT22 or similar.
    if not settings.enable_gpio:
        return None
    return None


def read_light_intensity() -> Optional[float]:
    # TODO: wire up a BH1750/LDR.
    if not settings.enable_gpio:
        return None
    return None
