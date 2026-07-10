"""AAS v2 agent entrypoint.

Run:   cd agent && python -m aas_agent.main            (uses ./config.yaml)
       python -m aas_agent.main /path/to/config.yaml

With mock_hardware: true this runs on any machine — synthetic sensors,
printed pump actions — which is exactly how you develop the web tier and
rehearse the demo without the rig powered on.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time

from .actuators import PumpController
from .config import AgentConfig, load_config
from .dosing import PlantMeasure, compute_doses
from .hal import build_pumps
from .irrigation import IrrigationLoop
from .models import SensorFrame
from .mqtt_bus import MqttBus
from .serial_reader import MockSerialReader, SerialReader
from .state import SharedState
from .store import Store

log = logging.getLogger("aas")


async def telemetry_pump(queue: asyncio.Queue, state: SharedState,
                         bus: MqttBus) -> None:
    """Move validated frames from the sensor source to state + MQTT."""
    while True:
        frame: SensorFrame = await queue.get()
        state.update(frame)
        payload = frame.model_dump(exclude={"received_at"})
        payload["ts"] = time.time()
        await bus.publish("telemetry", payload)


def register_commands(bus: MqttBus, controller: PumpController, store: Store,
                      irrigation: IrrigationLoop, cfg: AgentConfig) -> None:
    async def cmd_dose(p: dict) -> dict:
        """{"pump": "N", "ml": 40, "key": "uuid"} — one pump, one dose."""
        return dict(await controller.dose(
            str(p["pump"]), float(p["ml"]),
            reason=str(p.get("reason", "remote_command")),
            idempotency_key=p.get("key"),
        ))

    async def cmd_fertilize(p: dict) -> dict:
        """Full plan: measurements + deficiencies -> compute -> dose each pump.
        {"height_cm":120,"width_cm":80,"growth_stage":"vegetative",
         "deficiencies":["N","K"],"key":"uuid"}"""
        plant = PlantMeasure.model_validate(p)          # bounds-checked here
        doses = compute_doses(plant, list(p.get("deficiencies", [])),
                              max_dose_ml=cfg.safety.max_dose_ml)
        results = []
        for d in doses:
            key = f"{p['key']}:{d.nutrient}" if p.get("key") else None
            r = await controller.dose(d.nutrient, d.amount_ml,
                                      reason="fertigation_plan",
                                      idempotency_key=key)
            results.append(dict(r))
        return {"planned": [d.model_dump() for d in doses], "results": results}

    async def cmd_stop(p: dict) -> dict:
        await controller.emergency_stop()
        return {"stopped": True}

    async def cmd_resume(p: dict) -> dict:
        controller.resume()
        irrigation.reset_alarm()
        return {"resumed": True}

    async def cmd_tank_set(p: dict) -> dict:
        store.set_tank(str(p["nutrient"]), float(p["level_ml"]))
        levels = store.tank_levels()
        await bus.publish("tanks", levels, retain=True)
        return levels

    async def cmd_tank_get(p: dict) -> dict:
        return store.tank_levels()

    bus.register("dose", cmd_dose)
    bus.register("fertilize", cmd_fertilize)
    bus.register("stop", cmd_stop)
    bus.register("resume", cmd_resume)
    bus.register("tank_set", cmd_tank_set)
    bus.register("tank_get", cmd_tank_get)


async def run(cfg: AgentConfig) -> None:
    loop = asyncio.get_event_loop()
    store = Store(cfg.data_dir, cfg.tanks.default_level_ml,
                  [n for n in cfg.pumps if n != "water"])
    pumps = build_pumps(cfg.pumps, mock=cfg.mock_hardware)
    controller = PumpController(cfg, pumps, store)
    state = SharedState()
    bus = MqttBus(cfg.mqtt, cfg.node_id, store)
    controller.set_event_sink(lambda ev: bus.publish("events", ev))

    if cfg.mock_hardware:
        reader = MockSerialReader(cfg.serial, loop)
        state.mock_wet_soil = reader.wet_soil
    else:
        reader = SerialReader(cfg.serial, loop)

    irrigation = IrrigationLoop(cfg, state, controller,
                                emit_event=lambda ev: bus.publish("events", ev))
    register_commands(bus, controller, store, irrigation, cfg)

    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass  # e.g. Windows dev machine

    bus.start()
    reader.start()
    irrigation.start()
    pump_task = loop.create_task(telemetry_pump(reader.queue, state, bus))
    await bus.publish("tanks", store.tank_levels(), retain=True)
    log.info("agent %s up (mock=%s)", cfg.node_id, cfg.mock_hardware)

    await stop_event.wait()

    log.info("shutting down — forcing pumps off")
    await controller.emergency_stop()
    pump_task.cancel()
    irrigation.stop()
    reader.stop()
    await bus.stop()
    controller.close()
    store.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    cfg = load_config(cfg_path)
    asyncio.run(run(cfg))


if __name__ == "__main__":
    main()
