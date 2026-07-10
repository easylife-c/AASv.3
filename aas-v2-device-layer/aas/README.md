# AAS v2 — Device layer (Week 1)

Smart agriculture system: Arduino sensor hub + Raspberry Pi 5 hardware agent.
The agent owns **all** actuation safety; the web tier (Week 2/3) only requests.

```
aas/
├── firmware/sensor_hub/sensor_hub.ino   Arduino Uno: sensors -> framed JSON serial
├── agent/                               Pi agent (Python, asyncio)
│   ├── config.yaml                      all tunables + safety limits
│   └── aas_agent/                       source
└── docs/PROTOCOL.md                     serial + MQTT contract for the backend
```

## Quickstart — mock mode (any computer, zero hardware)

```bash
sudo apt install mosquitto mosquitto-clients     # or brew install mosquitto
cd agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m aas_agent.main                          # mock_hardware: true in config.yaml
```

Watch it live and poke it:

```bash
mosquitto_sub -t 'nodes/#' -v                     # all telemetry + events

# manual 40 mL nitrogen dose (idempotency key required)
mosquitto_pub -t nodes/node-1/cmd/dose \
  -m '{"pump":"N","ml":40,"key":"test-001","reason":"manual"}'

# full fertigation plan
mosquitto_pub -t nodes/node-1/cmd/fertilize \
  -m '{"height_cm":120,"width_cm":80,"growth_stage":"vegetative","deficiencies":["N","K"],"key":"plan-001"}'

# emergency stop / resume
mosquitto_pub -t nodes/node-1/cmd/stop -m '{}'
mosquitto_pub -t nodes/node-1/cmd/resume -m '{}'
```

The mock soil dries slowly; the irrigation loop will trigger on its own once
moisture debounces below `irrigation.moisture_dry_pct`. Send the same dose key
twice and note the pump does **not** run again — that's the idempotency guard.

## Deploying on the Pi 5

1. Flash the Arduino with `firmware/sensor_hub/sensor_hub.ino`
   (libraries: ModbusMaster, Adafruit SHT31, BH1750, Adafruit INA219, ArduinoJson v6).
2. Verify raw frames: `screen /dev/ttyACM0 115200` — you should see `$..*HH` lines.
3. In `agent/config.yaml`: set `mock_hardware: false`, confirm `serial.port`,
   and **calibrate `flow_ml_per_sec` per pump** (10 s into a measuring cup).
4. `pip install -r requirements.txt` (gpiozero ships with Raspberry Pi OS).
5. Run as a service so it survives reboots:

```ini
# /etc/systemd/system/aas-agent.service
[Unit]
Description=AAS hardware agent
After=network.target mosquitto.service

[Service]
WorkingDirectory=/home/pi/aas/agent
ExecStart=/home/pi/aas/agent/.venv/bin/python -m aas_agent.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`Restart=always` plus the agent's shutdown handler (pumps forced off) means a
crash never leaves a relay energized.

## Hardware bring-up checklist

- [ ] 7-in-1 sensor answers on Modbus (address 0x01, 4800 baud are the usual
      defaults — the register map in the sketch header notes vendor variations;
      if moisture and temperature look swapped, swap the register indices)
- [ ] SHT31 (0x44), BH1750 (0x23), INA219 (0x40) all appear in `i2cdetect` on the Uno side
- [ ] Common ground between the 12 V sensor supply, MAX485, and Arduino
- [ ] Each pump's real flow rate measured and written into config.yaml
- [ ] Relay board confirmed LOW-trigger (matches `active_high=False`); if yours
      is HIGH-trigger, flip it in `hal.py`
- [ ] Pull the USB cable mid-run: agent logs serial retry, keeps running,
      irrigation refuses stale data — this is a great judge demo
- [ ] Stop Mosquitto mid-run: telemetry buffers to SQLite, backfills on restart

## Second node

Copy `config.yaml`, set `node_id: node-2` and its own pins/serial port, run a
second agent instance. All topics are already namespaced per node.
