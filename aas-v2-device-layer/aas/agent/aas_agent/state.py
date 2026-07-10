"""Tiny shared-state holder: the most recent validated sensor frame.

Automation reads from here rather than from the queue directly, so multiple
consumers (irrigation loop, command handlers, future fertigation rules) always
see the same, freshest picture without racing each other for queue items.
"""

from __future__ import annotations

from typing import Callable

from .models import SensorFrame


class SharedState:
    def __init__(self) -> None:
        self.latest_frame: SensorFrame | None = None
        # Set in mock mode: lets the irrigation loop moisten the synthetic soil.
        self.mock_wet_soil: Callable[[], None] | None = None

    def update(self, frame: SensorFrame) -> None:
        self.latest_frame = frame
