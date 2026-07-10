"""MQTT connection to the rest of the system.

Design rules:
  - The agent never depends on the broker to stay safe: if MQTT is down,
    telemetry is buffered in SQLite and automation keeps running locally.
  - Last-will marks the node offline the moment the connection drops, so the
    dashboard always shows truthful node status.
  - Commands are dispatched to registered handlers; every command gets an ack
    on nodes/<id>/events, success or refusal.

Topics (full spec in docs/PROTOCOL.md):
  nodes/<id>/status        retained  "online"/"offline"
  nodes/<id>/telemetry               validated sensor frames
  nodes/<id>/tanks         retained  current tank levels
  nodes/<id>/events                  dose results, alarms, acks
  nodes/<id>/cmd/<action>            commands from the backend
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

from .config import MqttCfg
from .store import Store

log = logging.getLogger(__name__)

Handler = Callable[[dict], Awaitable[dict | None]]


class MqttBus:
    def __init__(self, cfg: MqttCfg, node_id: str, store: Store):
        self._cfg = cfg
        self._node = node_id
        self._store = store
        self._handlers: dict[str, Handler] = {}
        self._client = None
        self._connected = asyncio.Event()
        self._task: asyncio.Task | None = None

    # ---- topic helpers -------------------------------------------------------
    def t(self, suffix: str) -> str:
        return f"nodes/{self._node}/{suffix}"

    def register(self, action: str, handler: Handler) -> None:
        """Register a handler for nodes/<id>/cmd/<action>."""
        self._handlers[action] = handler

    # ---- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._task = asyncio.get_event_loop().create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        import aiomqtt

        will = aiomqtt.Will(self.t("status"), payload="offline", qos=1, retain=True)
        backoff = 1.0
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self._cfg.host,
                    port=self._cfg.port,
                    username=self._cfg.username,
                    password=self._cfg.password,
                    will=will,
                    keepalive=30,
                ) as client:
                    self._client = client
                    self._connected.set()
                    backoff = 1.0
                    log.info("MQTT connected to %s:%s", self._cfg.host, self._cfg.port)

                    await client.publish(self.t("status"), "online", qos=1, retain=True)
                    await client.subscribe(self.t("cmd/#"), qos=1)
                    asyncio.get_event_loop().create_task(self._drain_buffer())

                    async for message in client.messages:
                        await self._dispatch(str(message.topic),
                                             bytes(message.payload))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._connected.clear()
                self._client = None
                log.warning("MQTT down (%s) — reconnect in %.0fs; telemetry "
                            "buffering locally, automation unaffected", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    # ---- publishing ---------------------------------------------------------
    async def publish(self, suffix: str, payload: dict,
                      retain: bool = False, buffer_if_down: bool = True) -> None:
        topic = self.t(suffix)
        if self._client is not None and self._connected.is_set():
            try:
                await self._client.publish(topic, json.dumps(payload),
                                           qos=1, retain=retain)
                return
            except Exception:
                log.warning("publish failed, buffering %s", topic)
        if buffer_if_down:
            self._store.buffer_put(topic, payload)

    async def _drain_buffer(self) -> None:
        """Backfill telemetry that accumulated while offline."""
        while self._connected.is_set():
            rows = self._store.buffer_take(limit=100)
            if not rows:
                return
            done: list[int] = []
            for row_id, topic, payload in rows:
                try:
                    payload["backfilled"] = True
                    await self._client.publish(topic, json.dumps(payload), qos=1)
                    done.append(row_id)
                except Exception:
                    break
            self._store.buffer_delete(done)
            if len(done) < len(rows):
                return
            await asyncio.sleep(0.2)

    # ---- command dispatch ------------------------------------------------------
    async def _dispatch(self, topic: str, payload_bytes: bytes) -> None:
        action = topic.rsplit("/", 1)[-1]
        try:
            payload = json.loads(payload_bytes.decode("utf-8")) if payload_bytes else {}
        except json.JSONDecodeError:
            await self.publish("events", {"type": "cmd_ack", "action": action,
                                          "ok": False, "error": "bad_json"})
            return

        handler = self._handlers.get(action)
        if handler is None:
            await self.publish("events", {"type": "cmd_ack", "action": action,
                                          "ok": False, "error": "unknown_action"})
            return

        async def _run_handler() -> None:
            try:
                result = await handler(payload)
                await self.publish("events", {"type": "cmd_ack", "action": action,
                                              "ok": True, "result": result})
            except Exception as exc:
                log.exception("handler %s failed", action)
                await self.publish("events", {"type": "cmd_ack", "action": action,
                                              "ok": False, "error": str(exc)})

        # Handlers may take minutes (a dose); never block the message loop.
        asyncio.get_event_loop().create_task(_run_handler())
