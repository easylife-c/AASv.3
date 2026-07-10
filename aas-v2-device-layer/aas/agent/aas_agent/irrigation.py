"""Auto-irrigation loop.

The v1 loop would flood the plant if the moisture sensor stuck at 'dry'
(50 mL every 10 minutes, forever) — and for durian, waterlogged soil is a
Phytophthora invitation. This loop adds three guards on top of the
PumpController's own caps:

  1. Debounce      — N consecutive dry readings required, not one.
  2. Staleness     — refuses to act on telemetry older than the config limit.
  3. Effect check  — if moisture doesn't rise after max_no_effect_doses
                     consecutive doses, assume a stuck sensor or empty line,
                     raise an alarm, and stop until a human resets it.
"""

from __future__ import annotations

import asyncio
import logging

from .actuators import PumpController
from .config import AgentConfig
from .state import SharedState

log = logging.getLogger(__name__)


class IrrigationLoop:
    def __init__(self, cfg: AgentConfig, state: SharedState,
                 controller: PumpController, emit_event):
        self._cfg = cfg
        self._state = state
        self._controller = controller
        self._emit = emit_event
        self._dry_streak = 0
        self._no_effect_doses = 0
        self._moist_before_dose: float | None = None
        self._halted = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.get_event_loop().create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def reset_alarm(self) -> None:
        """Called via MQTT command after a human checks the hardware."""
        self._halted = False
        self._no_effect_doses = 0
        self._dry_streak = 0
        log.info("irrigation alarm reset by operator")

    @property
    def halted(self) -> bool:
        return self._halted

    async def _run(self) -> None:
        irr = self._cfg.irrigation
        while True:
            await asyncio.sleep(irr.check_interval_sec)
            try:
                await self._tick()
            except Exception:
                log.exception("irrigation tick failed")

    async def _tick(self) -> None:
        irr, safety = self._cfg.irrigation, self._cfg.safety

        if self._halted:
            return

        frame = self._state.latest_frame
        if frame is None or frame.soil is None:
            return
        if frame.age_sec > safety.telemetry_max_age_sec:
            log.warning("telemetry stale (%.0fs) — skipping irrigation decision",
                        frame.age_sec)
            return

        moist = frame.soil.moist

        # Effect check: did the previous dose actually move the needle?
        if self._moist_before_dose is not None:
            if moist <= self._moist_before_dose + 1.0:
                self._no_effect_doses += 1
                log.warning("dose had no measurable effect (%d/%d)",
                            self._no_effect_doses, irr.max_no_effect_doses)
                if self._no_effect_doses >= irr.max_no_effect_doses:
                    self._halted = True
                    await self._emit({
                        "type": "alarm", "code": "irrigation_no_effect",
                        "detail": ("moisture did not rise after "
                                   f"{self._no_effect_doses} doses — possible stuck "
                                   "sensor, empty line, or blocked emitter. "
                                   "Auto-irrigation halted until reset."),
                    })
                    return
            else:
                self._no_effect_doses = 0
            self._moist_before_dose = None

        # Debounce
        if moist < irr.moisture_dry_pct:
            self._dry_streak += 1
        else:
            self._dry_streak = 0
            return

        if self._dry_streak < irr.consecutive_dry_readings:
            return

        log.info("soil dry (%.1f%% for %d readings) — irrigating %.0f mL",
                 moist, self._dry_streak, irr.dose_ml)
        self._moist_before_dose = moist
        self._dry_streak = 0
        result = await self._controller.dose("water", irr.dose_ml,
                                             reason="auto_irrigation")
        if result["ok"]:
            # In mock mode, make the synthetic soil respond so demos look real.
            wet = getattr(self._state, "mock_wet_soil", None)
            if wet:
                wet()
