# AAS v2 — Device protocol specification

This is the contract between the three tiers. The Week 2 FastAPI backend builds
against exactly what is written here.

## 1. Serial link (Arduino Uno → Pi, USB, 115200 baud)

One frame per line, NMEA-style:

```
$<json>*HH\n
```

`HH` = two uppercase hex digits, XOR of every byte of `<json>`. The Pi discards
any line that fails the checksum (protects against partial lines from Arduino
resets and USB glitches).

Frame payload (sections are omitted when that sensor errored; codes go in `err`):

```json
{
  "seq": 1042,
  "soil":  {"moist": 34.2, "temp": 27.1, "ec": 812, "ph": 6.4, "n": 48, "p": 22, "k": 95},
  "air":   {"temp": 31.2, "rh": 68.5},
  "lux":   15400,
  "power": {"v": 12.1, "i_ma": 420},
  "err":   []
}
```

Units: moist %, temp °C, ec µS/cm, n/p/k mg/kg, rh %, lux lx, v volts, i_ma mA.
`seq` increments per frame; a gap means lost frames or an Arduino reset.

## 2. MQTT topics

All topics are namespaced per node: `nodes/<node_id>/...`. Two nodes = two
agents with different `node_id` values; nothing else changes.

| Topic | Dir | Retained | Payload |
|---|---|---|---|
| `nodes/<id>/status` | agent → | yes | `"online"` / `"offline"` (offline via last-will) |
| `nodes/<id>/telemetry` | agent → | no | validated sensor frame + `ts` (epoch sec); `backfilled: true` if replayed after an outage |
| `nodes/<id>/tanks` | agent → | yes | `{"N": 950.0, "P": 1000.0, "K": 872.5}` |
| `nodes/<id>/events` | agent → | no | dose results, alarms, command acks (below) |
| `nodes/<id>/cmd/<action>` | → agent | no | commands (below) |

## 3. Commands (`nodes/<id>/cmd/<action>`)

Every command is acknowledged on `nodes/<id>/events` as
`{"type": "cmd_ack", "action": ..., "ok": bool, "result"|"error": ...}`.

| Action | Payload | Notes |
|---|---|---|
| `dose` | `{"pump": "N", "ml": 40, "key": "<uuid>", "reason": "manual"}` | one pump, one dose |
| `fertilize` | `{"height_cm": 120, "width_cm": 80, "growth_stage": "vegetative", "deficiencies": ["N","K"], "key": "<uuid>"}` | agent computes doses and runs them sequentially |
| `stop` | `{}` | emergency stop: all relays off, further doses refused |
| `resume` | `{}` | clears emergency stop and irrigation no-effect alarm |
| `tank_set` | `{"nutrient": "N", "level_ml": 1000}` | after a physical refill |
| `tank_get` | `{}` | returns current levels |

**Idempotency:** `key` is any unique string (UUID). Re-sending a command with
the same key returns the original result and never re-runs the pumps. The
backend must always send a key for dose/fertilize so network retries are safe.

**Safety:** the agent may deliver *less* than requested (clamps) or refuse
entirely (cooldown, daily cap, empty tank, emergency stop). The dose result
always reports `requested_ml` vs `delivered_ml` and `refused_by`. The web tier
must display these truthfully rather than assuming success.

## 4. Event types on `nodes/<id>/events`

- `{"type": "dose_result", "ok": ..., "pump": ..., "requested_ml": ..., "delivered_ml": ..., "reason": ..., "refused_by": ...}`
- `{"type": "alarm", "code": "irrigation_no_effect", "detail": "..."}` — auto-irrigation halted itself; needs `resume` after a physical check
- `{"type": "emergency_stop"}`
- `{"type": "cmd_ack", ...}`
