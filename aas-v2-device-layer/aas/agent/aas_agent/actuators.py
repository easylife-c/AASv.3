"""Pump controller — the safety kernel of the whole system.

Every dose, whether requested by the web app, the scheduler, or the local
irrigation loop, goes through PumpController.dose(). Interlocks enforced here:

  1. Global mutex        — one pump at a time; no concurrent tank races.
  2. Volume clamp        — single dose capped at safety.max_dose_ml.
  3. Runtime clamp       — relay-on time capped at safety.max_pump_seconds,
                           independent of any volume math.
  4. Daily cap           — per-pump 24h volume ceiling (local farm day).
  5. Cooldown            — per-pump minimum interval between doses.
  6. Tank check          — atomic draw; nutrient doses fail if the tank lacks volume.
  7. Guaranteed off      — pump.off() in a finally block, plus off-on-shutdown.
  8. Idempotency         — a retried command (same key) never double-doses.
  9. Audit log           — every attempt recorded, allowed or refused.

The network and web tiers can request; they can never bypass this module.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Awaitable

from .config import AgentConfig
from .hal import Pump
from .store import Store

log = logging.getLogger(__name__)

NUTRIENT_PUMPS = {"N", "P", "K"}  # pumps that draw from a tracked tank


class DoseResult(dict):
    """Plain dict payload: {'ok': bool, 'pump', 'requested_ml', 'delivered_ml',
    'reason', 'refused_by' | None, 'detail'} — JSON-ready for MQTT events."""


class PumpController:
    def __init__(self, cfg: AgentConfig, pumps: dict[str, Pump], store: Store,
                 on_event: Callable[[dict], Awaitable[None]] | None = None):
        self._cfg = cfg
        self._pumps = pumps
        self._store = store
        self._lock = asyncio.Lock()
        self._on_event = on_event
        self._shutdown = False

    def set_event_sink(self, sink: Callable[[dict], Awaitable[None]]) -> None:
        self._on_event = sink

    async def _emit(self, event: dict) -> None:
        if self._on_event:
            try:
                await self._on_event(event)
            except Exception:
                log.exception("event sink failed")

    def _refuse(self, pump: str, ml: float, reason: str, why: str) -> DoseResult:
        self._store.log_dose(pump, ml, reason, ok=False, detail=why)
        log.warning("dose REFUSED pump=%s ml=%.1f reason=%s why=%s", pump, ml, reason, why)
        return DoseResult(ok=False, pump=pump, requested_ml=ml, delivered_ml=0.0,
                          reason=reason, refused_by=why, detail=why)

    async def dose(self, pump_name: str, ml: float, reason: str,
                   idempotency_key: str | None = None) -> DoseResult:
        # 8. idempotency: a retried command returns the original result
        if idempotency_key:
            prev = self._store.idem_get(idempotency_key)
            if prev is not None:
                log.info("idempotent replay for key=%s", idempotency_key)
                return DoseResult(**prev)

        result = await self._dose_inner(pump_name, ml, reason)

        if idempotency_key:
            self._store.idem_put(idempotency_key, dict(result))
        await self._emit({"type": "dose_result", **result})
        return result

    async def _dose_inner(self, pump_name: str, ml: float, reason: str) -> DoseResult:
        cfg, safety = self._cfg, self._cfg.safety

        if self._shutdown:
            return self._refuse(pump_name, ml, reason, "agent_shutting_down")
        if pump_name not in self._pumps:
            return self._refuse(pump_name, ml, reason, "unknown_pump")
        if not (0 < ml <= 100000):
            return self._refuse(pump_name, ml, reason, "invalid_volume")

        # 2. single-dose volume clamp
        requested = ml
        ml = min(ml, safety.max_dose_ml)

        # 3. runtime clamp — recompute deliverable volume from the time ceiling
        flow = cfg.pumps[pump_name].flow_ml_per_sec
        duration = ml / flow
        if duration > safety.max_pump_seconds:
            duration = safety.max_pump_seconds
            ml = duration * flow

        # 5. cooldown
        last = self._store.last_dose_ts(pump_name)
        if last is not None:
            elapsed = time.time() - last.timestamp()
            if elapsed < safety.min_seconds_between_doses:
                wait = int(safety.min_seconds_between_doses - elapsed)
                return self._refuse(pump_name, requested, reason, f"cooldown_{wait}s_left")

        # 4. daily cap
        used = self._store.daily_usage(pump_name)
        cap = safety.daily_cap_ml.get(pump_name, 0.0)
        if used + ml > cap:
            return self._refuse(pump_name, requested, reason,
                                f"daily_cap {used:.0f}+{ml:.0f}>{cap:.0f}ml")

        # 1. global mutex — from here on, we own the hardware
        async with self._lock:
            # 6. atomic tank draw for nutrient pumps
            if pump_name in NUTRIENT_PUMPS:
                if not self._store.draw_from_tank(pump_name, ml):
                    return self._refuse(pump_name, requested, reason, "tank_insufficient")

            pump = self._pumps[pump_name]
            started = time.monotonic()
            try:
                log.info("dose START pump=%s ml=%.1f dur=%.1fs reason=%s",
                         pump_name, ml, duration, reason)
                pump.on()
                await asyncio.sleep(duration)
            finally:
                # 7. the relay turns off no matter what happened above
                pump.off()

            actual = time.monotonic() - started
            self._store.add_daily_usage(pump_name, ml)
            self._store.log_dose(pump_name, ml, reason, ok=True,
                                 detail=f"run={actual:.1f}s")

        return DoseResult(ok=True, pump=pump_name, requested_ml=requested,
                          delivered_ml=round(ml, 1), reason=reason,
                          refused_by=None, detail=f"run={actual:.1f}s")

    async def emergency_stop(self) -> None:
        """Force every relay off. Safe to call from signal handlers/commands."""
        self._shutdown = True
        for name, pump in self._pumps.items():
            try:
                pump.off()
            except Exception:
                log.exception("failed to switch off pump %s", name)
        await self._emit({"type": "emergency_stop"})
        log.warning("EMERGENCY STOP — all pumps off")

    def resume(self) -> None:
        self._shutdown = False

    def close(self) -> None:
        for pump in self._pumps.values():
            try:
                pump.off()
                pump.close()
            except Exception:
                pass
