"""Durable local state on SQLite (WAL mode).

Replaces tank_levels.json / fertilizer_log.json, which could be corrupted by a
power cut mid-write. SQLite gives us atomic transactions, and doubles as the
telemetry buffer that lets the node keep working when the network is down.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

BANGKOK = timezone(timedelta(hours=7))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tanks (
    nutrient TEXT PRIMARY KEY,
    level_ml REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS daily_usage (
    day   TEXT NOT NULL,
    pump  TEXT NOT NULL,
    ml    REAL NOT NULL,
    PRIMARY KEY (day, pump)
);
CREATE TABLE IF NOT EXISTS dose_log (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT NOT NULL,
    pump   TEXT NOT NULL,
    ml     REAL NOT NULL,
    reason TEXT NOT NULL,
    ok     INTEGER NOT NULL,
    detail TEXT
);
CREATE TABLE IF NOT EXISTS telemetry_buffer (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    topic   TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
    key    TEXT PRIMARY KEY,
    ts     TEXT NOT NULL,
    result TEXT NOT NULL
);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_day() -> str:
    """Daily caps roll over at midnight farm-local time, not UTC."""
    return datetime.now(BANGKOK).strftime("%Y-%m-%d")


class Store:
    def __init__(self, data_dir: str, default_tank_ml: float, nutrients: list[str]):
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(
            str(Path(data_dir) / "agent.db"), check_same_thread=False
        )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(_SCHEMA)
        self._lock = threading.Lock()
        with self._lock, self._db:
            for n in nutrients:
                self._db.execute(
                    "INSERT OR IGNORE INTO tanks (nutrient, level_ml) VALUES (?, ?)",
                    (n, default_tank_ml),
                )

    # ---- tanks -------------------------------------------------------------
    def tank_levels(self) -> dict[str, float]:
        with self._lock:
            rows = self._db.execute("SELECT nutrient, level_ml FROM tanks").fetchall()
        return {n: lvl for n, lvl in rows}

    def set_tank(self, nutrient: str, level_ml: float) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO tanks (nutrient, level_ml) VALUES (?, ?) "
                "ON CONFLICT(nutrient) DO UPDATE SET level_ml = excluded.level_ml",
                (nutrient, max(0.0, level_ml)),
            )

    def draw_from_tank(self, nutrient: str, ml: float) -> bool:
        """Atomically subtract; refuses to go below zero. Returns success."""
        with self._lock, self._db:
            cur = self._db.execute(
                "UPDATE tanks SET level_ml = level_ml - ? "
                "WHERE nutrient = ? AND level_ml >= ?",
                (ml, nutrient, ml),
            )
            return cur.rowcount == 1

    # ---- daily usage caps ----------------------------------------------------
    def daily_usage(self, pump: str) -> float:
        with self._lock:
            row = self._db.execute(
                "SELECT ml FROM daily_usage WHERE day = ? AND pump = ?",
                (_local_day(), pump),
            ).fetchone()
        return row[0] if row else 0.0

    def add_daily_usage(self, pump: str, ml: float) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO daily_usage (day, pump, ml) VALUES (?, ?, ?) "
                "ON CONFLICT(day, pump) DO UPDATE SET ml = ml + excluded.ml",
                (_local_day(), pump, ml),
            )

    # ---- dose audit log --------------------------------------------------------
    def log_dose(self, pump: str, ml: float, reason: str, ok: bool, detail: str = "") -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO dose_log (ts, pump, ml, reason, ok, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (_utcnow(), pump, ml, reason, int(ok), detail),
            )

    def last_dose_ts(self, pump: str) -> datetime | None:
        with self._lock:
            row = self._db.execute(
                "SELECT ts FROM dose_log WHERE pump = ? AND ok = 1 ORDER BY id DESC LIMIT 1",
                (pump,),
            ).fetchone()
        return datetime.fromisoformat(row[0]) if row else None

    # ---- offline telemetry buffer -----------------------------------------------
    def buffer_put(self, topic: str, payload: dict) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO telemetry_buffer (ts, topic, payload) VALUES (?, ?, ?)",
                (_utcnow(), topic, json.dumps(payload)),
            )
            # Bound the buffer: keep the newest ~10k rows on a long outage.
            self._db.execute(
                "DELETE FROM telemetry_buffer WHERE id NOT IN "
                "(SELECT id FROM telemetry_buffer ORDER BY id DESC LIMIT 10000)"
            )

    def buffer_take(self, limit: int = 100) -> list[tuple[int, str, dict]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, topic, payload FROM telemetry_buffer ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [(i, t, json.loads(p)) for i, t, p in rows]

    def buffer_delete(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._lock, self._db:
            self._db.executemany(
                "DELETE FROM telemetry_buffer WHERE id = ?", [(i,) for i in ids]
            )

    # ---- idempotency ---------------------------------------------------------
    def idem_get(self, key: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "SELECT result FROM idempotency WHERE key = ?", (key,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def idem_put(self, key: str, result: dict) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO idempotency (key, ts, result) VALUES (?, ?, ?)",
                (key, _utcnow(), json.dumps(result)),
            )
            self._db.execute(
                "DELETE FROM idempotency WHERE ts < ?",
                ((datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),),
            )

    def close(self) -> None:
        self._db.close()
