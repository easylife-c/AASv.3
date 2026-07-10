"""Hardware abstraction layer.

Old code created gpiozero devices at import time, which made the modules
untestable off the Pi and crashed on pin conflicts. Here hardware is built
explicitly, behind an interface, with a mock twin for development and demos.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class Pump(ABC):
    @abstractmethod
    def on(self) -> None: ...

    @abstractmethod
    def off(self) -> None: ...

    @abstractmethod
    def is_on(self) -> bool: ...

    def close(self) -> None:  # optional cleanup
        pass


class MockPump(Pump):
    def __init__(self, name: str):
        self.name = name
        self._on = False

    def on(self) -> None:
        self._on = True
        log.info("[MOCK] pump %s ON", self.name)

    def off(self) -> None:
        self._on = False
        log.info("[MOCK] pump %s OFF", self.name)

    def is_on(self) -> bool:
        return self._on


class GpioPump(Pump):
    """Relay-driven pump. active_high=False matches common LOW-trigger relay boards."""

    def __init__(self, name: str, pin: int):
        from gpiozero import OutputDevice  # imported lazily: only needed on the Pi

        self.name = name
        self._dev = OutputDevice(pin, active_high=False, initial_value=False)

    def on(self) -> None:
        self._dev.on()

    def off(self) -> None:
        self._dev.off()

    def is_on(self) -> bool:
        return bool(self._dev.value)

    def close(self) -> None:
        self._dev.off()
        self._dev.close()


def build_pumps(pump_cfg: dict, mock: bool) -> dict[str, Pump]:
    if mock:
        return {name: MockPump(name) for name in pump_cfg}
    return {name: GpioPump(name, cfg.pin) for name, cfg in pump_cfg.items()}
