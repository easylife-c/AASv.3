"""Arduino serial link.

Reads `$<json>*HH` frames from the Uno, verifies the XOR checksum, validates
with the pydantic models, and hands clean frames to the asyncio world through
a queue. Runs in its own thread so a wedged USB port can never stall the event
loop. Survives unplug/replug (reconnect with backoff) and Arduino resets
(partial lines fail the checksum and are discarded; seq gaps are logged).

Mock mode generates a realistic slow-moving synthetic farm so the whole stack
can be demoed with zero hardware attached.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
import threading
import time

from .config import SerialCfg
from .models import SensorFrame, parse_frame

log = logging.getLogger(__name__)


def _checksum_ok(line: str) -> tuple[bool, str]:
    if not line.startswith("$") or "*" not in line:
        return False, ""
    payload, _, hexsum = line[1:].rpartition("*")
    if len(hexsum) != 2:
        return False, ""
    try:
        expected = int(hexsum, 16)
    except ValueError:
        return False, ""
    actual = 0
    for ch in payload.encode("utf-8", errors="replace"):
        actual ^= ch
    return actual == expected, payload


class SerialReader:
    """Real hardware source. Frames arrive on `self.queue` (asyncio.Queue)."""

    def __init__(self, cfg: SerialCfg, loop: asyncio.AbstractEventLoop):
        self._cfg = cfg
        self._loop = loop
        self.queue: asyncio.Queue[SensorFrame] = asyncio.Queue(maxsize=100)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_seq: int | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="serial")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        import serial  # pyserial

        while not self._stop.is_set():
            try:
                with serial.Serial(self._cfg.port, self._cfg.baud, timeout=2) as port:
                    log.info("serial connected on %s", self._cfg.port)
                    port.reset_input_buffer()
                    while not self._stop.is_set():
                        raw = port.readline()
                        if not raw:
                            continue
                        self._handle_line(raw.decode("utf-8", errors="replace").strip())
            except serial.SerialException as exc:
                log.warning("serial error (%s) — retrying in 5s", exc)
                time.sleep(5)

    def _handle_line(self, line: str) -> None:
        if not line:
            return
        ok, payload = _checksum_ok(line)
        if not ok:
            log.debug("bad checksum / partial line dropped: %.60s", line)
            return
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            log.debug("unparseable frame dropped")
            return

        frame, dropped = parse_frame(raw)
        if frame is None:
            log.warning("frame failed validation entirely")
            return
        if dropped:
            log.warning("dropped out-of-range sections: %s (seq=%s)", dropped, frame.seq)
        if self._last_seq is not None and frame.seq not in (0, self._last_seq + 1):
            log.warning("seq gap: %s -> %s (Arduino reset or lost frames)",
                        self._last_seq, frame.seq)
        self._last_seq = frame.seq

        def _put() -> None:
            if self.queue.full():
                try:
                    self.queue.get_nowait()  # drop oldest, keep newest
                except asyncio.QueueEmpty:
                    pass
            self.queue.put_nowait(frame)

        self._loop.call_soon_threadsafe(_put)


class MockSerialReader:
    """Synthetic sensor source with day/night light cycles and slowly drying
    soil, so dashboards and automation behave believably in demos."""

    def __init__(self, cfg: SerialCfg, loop: asyncio.AbstractEventLoop,
                 interval_sec: float = 5.0):
        self.queue: asyncio.Queue[SensorFrame] = asyncio.Queue(maxsize=100)
        self._interval = interval_sec
        self._task: asyncio.Task | None = None
        self._seq = 0
        self._moist = 45.0

    def start(self) -> None:
        self._task = asyncio.get_event_loop().create_task(self._run())

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def wet_soil(self, amount_pct: float = 12.0) -> None:
        """Called by the mock pump path so irrigation visibly 'works' in demos."""
        self._moist = min(95.0, self._moist + amount_pct)

    async def _run(self) -> None:
        while True:
            hour = time.localtime().tm_hour + time.localtime().tm_min / 60
            daylight = max(0.0, math.sin((hour - 6) / 12 * math.pi))
            self._moist = max(8.0, self._moist - random.uniform(0.05, 0.3))

            raw = {
                "seq": self._seq,
                "soil": {
                    "moist": round(self._moist + random.uniform(-0.5, 0.5), 1),
                    "temp": round(27 + 4 * daylight + random.uniform(-0.3, 0.3), 1),
                    "ec": round(850 + random.uniform(-30, 30)),
                    "ph": round(6.3 + random.uniform(-0.1, 0.1), 2),
                    "n": round(55 + random.uniform(-3, 3)),
                    "p": round(28 + random.uniform(-2, 2)),
                    "k": round(110 + random.uniform(-5, 5)),
                },
                "air": {
                    "temp": round(28 + 6 * daylight + random.uniform(-0.5, 0.5), 1),
                    "rh": round(75 - 15 * daylight + random.uniform(-2, 2), 1),
                },
                "lux": round(90000 * daylight + random.uniform(0, 200), 0),
                "power": {"v": round(12.2 + random.uniform(-0.1, 0.1), 2),
                          "i_ma": round(380 + random.uniform(-20, 20), 1)},
                "err": [],
            }
            self._seq += 1
            frame, _ = parse_frame(raw)
            if frame:
                if self.queue.full():
                    self.queue.get_nowait()
                self.queue.put_nowait(frame)
            await asyncio.sleep(self._interval)
