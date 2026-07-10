/*
 * AAS v2 — Arduino Uno R3 sensor hub
 *
 * Role: read all sensors, emit one framed JSON line over USB serial every
 * READ_INTERVAL_MS. No actuation logic lives here — the Pi agent decides.
 *
 * Frame format (NMEA-style):   $<json>*HH\n
 *   HH = two uppercase hex digits, XOR of every byte in <json>.
 *   The Pi rejects any line whose checksum does not match, which protects
 *   against partial lines after an Arduino reset or USB glitch.
 *
 * Wiring:
 *   7-in-1 soil sensor (RS485 / Modbus RTU)
 *     Sensor A -> MAX485 A, Sensor B -> MAX485 B
 *     MAX485 RO -> D2, DI -> D3, DE+RE (tied together) -> D4
 *     Sensor power: 12V supply, common GND with Arduino.
 *   SHT31  (air temp/RH)   -> I2C (A4 SDA, A5 SCL), addr 0x44
 *   BH1750 (light, lux)    -> I2C, addr 0x23
 *   INA219 (volt/current)  -> I2C, addr 0x40, in series with the load you meter
 *
 * Libraries (Library Manager): ModbusMaster, Adafruit SHT31, BH1750 (claws),
 *   Adafruit INA219, ArduinoJson (v6).
 *
 * IMPORTANT — verify against YOUR sensor's datasheet:
 * Most JXCT-style 7-in-1 probes use slave address 0x01, 4800 baud 8N1, and
 * holding registers 0x0000..0x0006 = moisture, temperature, EC, pH, N, P, K.
 * Some vendors swap moisture/temperature or use 9600 baud. Adjust the
 * constants below if your readings look transposed.
 */

#include <SoftwareSerial.h>
#include <ModbusMaster.h>
#include <Wire.h>
#include <Adafruit_SHT31.h>
#include <BH1750.h>
#include <Adafruit_INA219.h>
#include <ArduinoJson.h>

// ---- configuration ---------------------------------------------------------
#define RS485_RX_PIN     2      // MAX485 RO
#define RS485_TX_PIN     3      // MAX485 DI
#define RS485_DE_RE_PIN  4      // MAX485 DE + RE tied together
#define SOIL_SLAVE_ADDR  1
#define SOIL_BAUD        4800
#define SOIL_REG_BASE    0x0000
#define SOIL_REG_COUNT   7      // moist, temp, EC, pH, N, P, K
#define READ_INTERVAL_MS 5000UL
#define HOST_BAUD        115200

// ---- devices ---------------------------------------------------------------
SoftwareSerial rs485(RS485_RX_PIN, RS485_TX_PIN);
ModbusMaster    soil;
Adafruit_SHT31  sht31;
BH1750          luxMeter;
Adafruit_INA219 ina219;

bool shtOk = false, luxOk = false, inaOk = false;
uint32_t seqNum = 0;
unsigned long lastRead = 0;

void preTransmission()  { digitalWrite(RS485_DE_RE_PIN, HIGH); }
void postTransmission() { digitalWrite(RS485_DE_RE_PIN, LOW);  }

void setup() {
  pinMode(RS485_DE_RE_PIN, OUTPUT);
  digitalWrite(RS485_DE_RE_PIN, LOW);

  Serial.begin(HOST_BAUD);          // USB link to the Raspberry Pi
  rs485.begin(SOIL_BAUD);

  soil.begin(SOIL_SLAVE_ADDR, rs485);
  soil.preTransmission(preTransmission);
  soil.postTransmission(postTransmission);

  Wire.begin();
  shtOk = sht31.begin(0x44);
  luxOk = luxMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  inaOk = ina219.begin();
}

void loop() {
  unsigned long now = millis();
  if (now - lastRead < READ_INTERVAL_MS && seqNum > 0) return;
  lastRead = now;

  StaticJsonDocument<512> doc;
  doc["seq"] = seqNum++;
  JsonArray err = doc.createNestedArray("err");

  // ---- soil 7-in-1 over Modbus ----
  uint8_t rc = soil.readHoldingRegisters(SOIL_REG_BASE, SOIL_REG_COUNT);
  if (rc == soil.ku8MBSuccess) {
    JsonObject s = doc.createNestedObject("soil");
    s["moist"] = soil.getResponseBuffer(0) / 10.0;             // %
    s["temp"]  = (int16_t)soil.getResponseBuffer(1) / 10.0;    // degC, signed
    s["ec"]    = soil.getResponseBuffer(2);                    // uS/cm
    s["ph"]    = soil.getResponseBuffer(3) / 10.0;
    s["n"]     = soil.getResponseBuffer(4);                    // mg/kg
    s["p"]     = soil.getResponseBuffer(5);                    // mg/kg
    s["k"]     = soil.getResponseBuffer(6);                    // mg/kg
  } else {
    err.add("soil");
  }

  // ---- SHT31 air temp / humidity ----
  if (shtOk) {
    float t = sht31.readTemperature();
    float h = sht31.readHumidity();
    if (!isnan(t) && !isnan(h)) {
      JsonObject a = doc.createNestedObject("air");
      a["temp"] = t;
      a["rh"]   = h;
    } else {
      err.add("sht31");
    }
  } else {
    err.add("sht31_init");
  }

  // ---- BH1750 light ----
  if (luxOk) {
    float lx = luxMeter.readLightLevel();
    if (lx >= 0) doc["lux"] = lx; else err.add("bh1750");
  } else {
    err.add("bh1750_init");
  }

  // ---- INA219 voltage / current ----
  if (inaOk) {
    JsonObject p = doc.createNestedObject("power");
    p["v"]    = ina219.getBusVoltage_V();
    p["i_ma"] = ina219.getCurrent_mA();
  } else {
    err.add("ina219_init");
  }

  // ---- frame + checksum ----
  char buf[512];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  uint8_t cksum = 0;
  for (size_t i = 0; i < n; i++) cksum ^= (uint8_t)buf[i];

  Serial.print('$');
  Serial.print(buf);
  Serial.print('*');
  if (cksum < 0x10) Serial.print('0');
  Serial.println(cksum, HEX);
}
