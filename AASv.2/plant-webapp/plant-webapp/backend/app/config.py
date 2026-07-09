"""
Centralized configuration. Replaces all hardcoded secrets/constants that used
to live directly in bot.py and main.py (Discord token, Gemini key, GPIO pins,
tank defaults, etc). Everything is now sourced from environment variables / .env.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./plant_app.db"

    # Gemini AI
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Auth
    secret_key: str = "insecure-default-change-me"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    # Hardware
    enable_gpio: bool = False
    moisture_pin: int = 25
    water_pump_pin: int = 27
    pump_pin_n: int = 22
    pump_pin_p: int = 23
    pump_pin_k: int = 24
    pump_rate_ml_per_sec: float = 8.5

    # App
    timezone: str = "Asia/Bangkok"
    cors_origins: str = "http://localhost:3000"
    fertilizer_cooldown_hours: float = 6.0
    default_tank_level_ml: float = 1000.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def pump_pins(self) -> dict[str, int]:
        return {"N": self.pump_pin_n, "P": self.pump_pin_p, "K": self.pump_pin_k}


settings = Settings()
