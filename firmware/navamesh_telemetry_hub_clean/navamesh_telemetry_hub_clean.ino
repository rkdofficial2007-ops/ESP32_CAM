#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <SPI.h>
#include <RF24.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_BMP280.h>
#include <Adafruit_Sensor.h>

// ── Wi-Fi & Network ───────────────────────────────────────────────────────────
const char* ssid     = "Kanha";
const char* password = "12345678";
IPAddress laptopIP(10, 151, 213, 196);     // dashboard laptop (auto-updates to the real laptop IP on first connect)

// ── Pins ──────────────────────────────────────────────────────────────────────
#define LED_PIN  2
#define NRF_SCK  14
#define NRF_MISO 25
#define NRF_MOSI 13
#define NRF_CE   4
#define NRF_CSN  5

SPIClass hspi(HSPI);
RF24 radio(NRF_CE, NRF_CSN);
Adafruit_MPU6050 mpu;
Adafruit_BMP280 bmp;
WebServer server(80);

bool nrfConnected = false;
bool mpuOnline = false;
bool bmpOnline = false;
unsigned long lastDashboardRequest = 0;   // time of last /data request from the dashboard

// ── Embedded Web Page ─────────────────────────────────────────────────────────
const char HTTP_WEBPAGE[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Telemetry Hub</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { background-color: #0b0e14; color: #00FF66; font-family: 'Courier New', monospace; padding: 20px; text-align: center; margin: 0; }
    h2 { color: #00E5FF; font-size: 24px; margin: 10px 0 20px 0; }
    .grid { display: flex; flex-wrap: wrap; justify-content: center; max-width: 800px; margin: 0 auto; }
    .card { background: #121824; border: 1px solid #1f293d; padding: 15px; margin: 10px; width: 45%; min-width: 280px; border-radius: 8px; font-size: 16px; text-align: left; box-sizing: border-box; }
    .card-title { font-weight: bold; color: #FFD700; font-size: 18px; margin-bottom: 10px; border-bottom: 1px solid #1f293d; padding-bottom: 5px; }
    .status-ok { color: #00FF66; font-weight: bold; }
    .status-warn { color: #FF3333; font-weight: bold; }
  </style>
</head>
<body>
  <h2>🛰️ ESP32 TELEMETRY HUB</h2>
  <div class="grid">
    <div class="card">
      <div class="card-title">📡 Network & Sensors</div>
      <div id="sys-data">Checking...</div>
    </div>
    <div class="card">
      <div class="card-title">📐 IMU Attitude (MPU6050)</div>
      <div id="imu-data">Loading IMU Data...</div>
    </div>
    <div class="card">
      <div class="card-title">🌡️ Barometer (BMP280)</div>
      <div id="bmp-data">Loading Atmosphere Data...</div>
    </div>
  </div>

  <script>
    function tag(ok, yes, no) {
      return ok ? "<span class='status-ok'>" + yes + "</span>" : "<span class='status-warn'>" + no + "</span>";
    }
    setInterval(function() {
      fetch('/data')
        .then(response => response.json())
        .then(data => {
          document.getElementById('sys-data').innerHTML =
            "<b>ESP32 IP:</b> " + data.ip + "<br>" +
            "<b>Dashboard Laptop:</b> " + data.laptop + "<br>" +
            "<b>NRF24L01:</b> " + tag(data.nrf === "CONNECTED", "CONNECTED", "DISCONNECTED") + "<br>" +
            "<b>MPU6050:</b> " + tag(data.mpu === "ONLINE", "ONLINE", "NOT FOUND") + "<br>" +
            "<b>BMP280:</b> " + tag(data.bmp === "ONLINE", "ONLINE", "NOT FOUND");

          document.getElementById('imu-data').innerHTML =
            "<b>Accel X:</b> " + data.ax + " g<br><b>Accel Y:</b> " + data.ay +
            " g<br><b>Accel Z:</b> " + data.az + " g<br><b>Gyro X:</b> " + data.gx + " deg/s" +
            "<br><b>Roll:</b> " + data.roll + "°<br><b>Pitch:</b> " + data.pitch + "°";

          document.getElementById('bmp-data').innerHTML =
            "<b>Temp:</b> " + data.temp + " °C<br><b>Pressure:</b> " + data.pres +
            " hPa<br><b>Altitude:</b> " + data.alt + " m";
        });
    }, 1000);
  </script>
</body>
</html>
)rawliteral";

// ── /data JSON (read by the NAVAMESH dashboard) ───────────────────────────────
void handleDataRequest() {
  lastDashboardRequest = millis();
  laptopIP = server.client().remoteIP();   // IP of whoever is reading the data (your laptop)

  float axg = 0.0, ayg = 0.0, azg = 1.0, gxd = 0.0;
  float roll = 0.0, pitch = 0.0, tilt = 0.0;
  if (mpuOnline) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    axg = a.acceleration.x / 9.80665F;
    ayg = a.acceleration.y / 9.80665F;
    azg = a.acceleration.z / 9.80665F;
    gxd = g.gyro.x * 180.0 / PI;
    roll  = atan2(ayg, azg) * 180.0 / PI;
    pitch = atan2(-axg, sqrt(ayg * ayg + azg * azg)) * 180.0 / PI;
    tilt  = sqrt(roll * roll + pitch * pitch);
  }

  float bTemp = bmpOnline ? bmp.readTemperature() : 28.0;
  float bPres = bmpOnline ? bmp.readPressure() / 100.0F : 1013.25;
  float bAlt  = bmpOnline ? bmp.readAltitude(1013.25) : 0.0;

  String json = "{";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"laptop\":\"" + laptopIP.toString() + "\",";
  json += "\"ax\":\"" + String(axg, 2) + "\",";
  json += "\"ay\":\"" + String(ayg, 2) + "\",";
  json += "\"az\":\"" + String(azg, 2) + "\",";
  json += "\"gx\":\"" + String(gxd, 2) + "\",";
  json += "\"roll\":\"" + String(roll, 1) + "\",";
  json += "\"pitch\":\"" + String(pitch, 1) + "\",";
  json += "\"tilt\":\"" + String(tilt, 1) + "\",";
  json += "\"temp\":\"" + String(bTemp, 1) + "\",";
  json += "\"pres\":\"" + String(bPres, 1) + "\",";
  json += "\"alt\":\"" + String(bAlt, 1) + "\",";
  json += "\"mpu\":\"" + String(mpuOnline ? "ONLINE" : "OFFLINE") + "\",";
  json += "\"bmp\":\"" + String(bmpOnline ? "ONLINE" : "OFFLINE") + "\",";
  json += "\"nrf\":\"" + String(nrfConnected ? "CONNECTED" : "DISCONNECTED") + "\"";
  json += "}";

  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

// ── setup() ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  Wire.begin(21, 22);

  mpuOnline = mpu.begin(0x68) || mpu.begin(0x69);
  if (mpuOnline) mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  bmpOnline = bmp.begin(0x76) || bmp.begin(0x77);

  hspi.begin(NRF_SCK, NRF_MISO, NRF_MOSI, NRF_CSN);
  nrfConnected = radio.begin(&hspi) && radio.isChipConnected();

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH); delay(200);
    digitalWrite(LED_PIN, LOW);  delay(200);
  }
  digitalWrite(LED_PIN, HIGH);

  server.on("/", []() { server.send(200, "text/html", HTTP_WEBPAGE); });
  server.on("/data", handleDataRequest);
  server.begin();
}

// ── loop() ────────────────────────────────────────────────────────────────────
void loop() {
  server.handleClient();

  // Reconnect automatically if the hotspot drops
  if (WiFi.status() != WL_CONNECTED) {
    static unsigned long lastTry = 0;
    if (millis() - lastTry > 5000) {
      lastTry = millis();
      WiFi.disconnect();
      WiFi.begin(ssid, password);
    }
  }

  // Serial Monitor: 200 = dashboard connected (polled /data in last 3 s), 0 = not connected
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint >= 1000) {
    lastPrint = millis();
    bool dashboardConnected = (lastDashboardRequest != 0) && (millis() - lastDashboardRequest < 3000);
    Serial.println(dashboardConnected ? 200 : 0);
  }
}
