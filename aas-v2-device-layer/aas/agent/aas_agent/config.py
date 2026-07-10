"""Typed configuration. A wrong config should crash at startup, never mid-dose."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class SerialCfg(BaseModel):
    port: str = "/dev/ttyACM0"
    baud: int = 115200
    frame_timeout_sec: float = 20.0


class MqttCfg(BaseModel):
    host: str = "localhost"
    port: int = 1883
    username: str | None = None
    password: str | None = None


class PumpCfg(BaseModel):
    pin: int
    flow_ml_per_sec: float = Field(gt=0.1, lt=100.0)


class SafetyCfg(BaseModel):
    max_pump_seconds: float = Field(default=90.0, gt=0, le=600)
    max_dose_ml: float = Field(default=500.0, gt=0)
    daily_cap_ml: dict[str, float]
    min_seconds_between_doses: float = Field(default=3600.0, ge=0)
    telemetry_max_age_sec: float = Field(default=60.0, gt=0)


class IrrigationCfg(BaseModel):
    moisture_dry_pct: float = Field(default=30.0, ge=0, le=100)
    consecutive_dry_readings: int = Field(default=3, ge=1)
    dose_ml: float = Field(default=200.0, gt=0)
    check_interval_sec: float = Field(default=600.0, ge=10)
    max_no_effect_doses: int = Field(default=3, ge=1)


class TanksCfg(BaseModel):
    default_level_ml: float = Field(default=1000.0, gt=0)


class AgentConfig(BaseModel):
    node_id: str
    mock_hardware: bool = True
    data_dir: str = "./data"
    serial: SerialCfg = SerialCfg()
    mqtt: MqttCfg = MqttCfg()
    pumps: dict[str, PumpCfg]
    safety: SafetyCfg
    irrigation: IrrigationCfg = IrrigationCfg()
    tanks: TanksCfg = TanksCfg()

    @field_validator("pumps")
    @classmethod
    def water_pump_required(cls, v: dict[str, PumpCfg]) -> dict[str, PumpCfg]:
        if "water" not in v:
            raise ValueError("config must define a 'water' pump")
        pins = [p.pin for p in v.values()]
        if len(pins) != len(set(pins)):
            raise ValueError("two pumps share the same GPIO pin")
        return v

    def model_post_init(self, __context) -> None:
        missing = set(self.pumps) - set(self.safety.daily_cap_ml)
        if missing:
            raise ValueError(f"safety.daily_cap_ml missing entries for: {missing}")


def load_config(path: str | Path = "config.yaml") -> AgentConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AgentConfig.model_validate(raw)
