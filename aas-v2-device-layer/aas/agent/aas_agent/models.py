"""Telemetry validation models.

Every frame from the Arduino is validated field-by-field before it can reach
automation or the network. Out-of-range values (a floating RS485 line reading
pH 25.5, EC spikes from wiring noise) are dropped per-field, not per-frame, so
one bad sensor never blinds the others. Week 2 reuses these exact models in
the FastAPI backend — one schema, two ends of the wire.
"""

from __future__ import annotations

import time
from pydantic import BaseModel, Field, ValidationError


class SoilReading(BaseModel):
    moist: float = Field(ge=0, le=100)        # %
    temp: float = Field(ge=-10, le=70)        # degC
    ec: float = Field(ge=0, le=20000)         # uS/cm
    ph: float = Field(ge=2, le=12)
    n: float = Field(ge=0, le=3000)           # mg/kg
    p: float = Field(ge=0, le=3000)
    k: float = Field(ge=0, le=3000)


class AirReading(BaseModel):
    temp: float = Field(ge=-10, le=70)        # degC
    rh: float = Field(ge=0, le=100)           # %


class PowerReading(BaseModel):
    v: float = Field(ge=0, le=30)             # volts
    i_ma: float = Field(ge=-10000, le=10000)  # milliamps


class SensorFrame(BaseModel):
    seq: int
    soil: SoilReading | None = None
    air: AirReading | None = None
    lux: float | None = Field(default=None, ge=0, le=200000)
    power: PowerReading | None = None
    err: list[str] = []
    received_at: float = 0.0                  # agent-side monotonic timestamp

    @property
    def age_sec(self) -> float:
        return time.monotonic() - self.received_at


def parse_frame(raw: dict) -> tuple[SensorFrame | None, list[str]]:
    """Validate a decoded frame. Invalid sections are dropped individually and
    reported; returns (frame, dropped_sections). Frame is None only if even
    the envelope (seq) is unusable."""
    dropped: list[str] = []
    cleaned: dict = {"seq": raw.get("seq", -1), "err": raw.get("err", [])}

    for section, model in (("soil", SoilReading), ("air", AirReading),
                           ("power", PowerReading)):
        if section in raw and raw[section] is not None:
            try:
                cleaned[section] = model.model_validate(raw[section])
            except ValidationError:
                dropped.append(section)

    if "lux" in raw and raw["lux"] is not None:
        try:
            cleaned["lux"] = float(raw["lux"])
            if not (0 <= cleaned["lux"] <= 200000):
                raise ValueError
        except (TypeError, ValueError):
            cleaned.pop("lux", None)
            dropped.append("lux")

    try:
        frame = SensorFrame.model_validate(cleaned)
    except ValidationError:
        return None, ["frame"]
    frame.received_at = time.monotonic()
    return frame, dropped
