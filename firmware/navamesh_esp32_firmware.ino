/*
  =============================================================================
  NAVAMESH ESP32 TELEMETRY FIRMWARE (EST. 2025) - HACKATHON EDITION
  Target Board : ESP32-WROOM-32D / ESP32-CAM
  Active Sensors:
    1. BMP280 Barometer (Pressure, Altitude, Temperature) [I2C: SDA=21, SCL=22]
    2. MPU6050 6-Axis IMU (Accel & Gyroscope Pitch/Roll/Tilt) [I2C: SDA=21, SCL=22]
    3. NRF24L01+ 2.4GHz Transceiver [HSPI: SCK=14, MISO=25, MOSI=13, CE=4, CSN=5]
  Network:
    - Wi-Fi Station Mode (SSID: "Sesa", PASS: "Megamind")
    - Embedded JSON Telemetry Server on Port 80 (/data)
    - USB High-Speed Serial Telemetry @ 115200 Baud
  =============================================================================
*/

#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <SPI.h>
#include <RF24.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_BMP280.h>

// ── Wi-Fi Credentials ─────────────────────────────────────────────────────────
const char* ssid     = "Sesa";
const char* password = "Megamind";

// ── Onboard LED ───────────────────────────────────────────────────────────────
#define LED_PIN 2

// ── NRF24L01 Pin Mapping (HSPI Bus) ───────────────────────────────────────────
#define NRF_SCK  14
#define NRF_MISO 25
#define NRF_MOSI 13
#define NRF_CE   4
#define NRF_CSN  5

SPIClass hspi(HSPI);
RF24 radio(NRF_CE, NRF_CSN);

// ── Sensor Objects & Web Server (Default Port 80) ─────────────────────────────
Adafruit_MPU6050 mpu;
Adafruit_BMP280  bmp;
WebServer server(80); // ESP32 acts as the web server on standard port 80

// ── Telemetry Globals ─────────────────────────────────────────────────────────
bool bmpOnline    = false;
bool mpuOnline    = false;
bool nrfConnected = false;

float roll  = 0.0;
float pitch = 0.0;
float yaw   = 0.0;
float tilt  = 0.0;
unsigned long lastReadTime = 0;

// ── Web Server JSON Data Handler (/data) ───────────────────────────────────────
void handleDataRequest() {
  sensors_event_t a, g, temp;
  float ax = 0.0, ay = 0.0, az = 1.0;
  float gx = 0.0;
  
  if (mpuOnline) {
    mpu.getEvent(&a, &g, &temp);
    ax = a.acceleration.x / 9.80665F; // m/s^2 to g
    ay = a.acceleration.y / 9.80665F;
    az = a.acceleration.z / 9.80665F;
    gx = g.gyro.x * 180.0 / PI;

    // Pitch & Roll Calculation in degrees
    roll  = atan2(ay, az) * 180.0 / PI;
    pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;
    tilt  = sqrt(roll * roll + pitch * pitch);
  }

  float bmpTemp  = 28.0;
  float bmpPres  = 1013.25;
  float bmpAlt   = 0.0;

  if (bmpOnline) {
    bmpTemp = bmp.readTemperature();
    bmpPres = bmp.readPressure() / 100.0F; // Pa to hPa
    bmpAlt  = bmp.readAltitude(1013.25);
  }

  // Build JSON payload consumed directly by NAVAMESH Dashboard
  String json = "{";
  json += "\"temp\":\"" + String(bmpTemp, 1) + "\",";
  json += "\"pres\":\"" + String(bmpPres, 1) + "\",";
  json += "\"alt\":\""  + String(bmpAlt, 1)  + "\",";
  json += "\"ax\":\""   + String(ax, 2)      + "\",";
  json += "\"ay\":\""   + String(ay, 2)      + "\",";
  json += "\"az\":\""   + String(az, 2)      + "\",";
  json += "\"gx\":\""   + String(gx, 2)      + "\",";
  json += "\"roll\":\"" + String(roll, 1)    + "\",";
  json += "\"pitch\":\""+ String(pitch, 1)   + "\",";
  json += "\"yaw\":\""  + String(yaw, 1)     + "\",";
  json += "\"tilt\":\"" + String(tilt, 1)    + "\",";
  json += "\"nrf\":\""  + String(nrfConnected ? "CONNECTED" : "DISCONNECTED") + "\"";
  json += "}";

  // Enable CORS so browser dashboard can access directly
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "application/json", json);
}

// ── Root Web Status Page (Port 80) ────────────────────────────────────────────
void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>NAVAMESH ESP32</title>";
  html += "<style>body{background:#020503;color:#00ff55;font-family:monospace;text-align:center;padding:40px;}";
  html += "h1{color:#10f543;text-shadow:0 0 10px #00ff55;}a{color:#00e5ff;font-size:18px;}</style></head><body>";
  html += "<h1>🔱 NAVAMESH ESP32 TELEMETRY NODE (PORT 80)</h1>";
  html += "<p>BMP280: " + String(bmpOnline ? "ONLINE" : "CHECK WIRING") + "</p>";
  html += "<p>MPU6050: " + String(mpuOnline ? "ONLINE" : "CHECK WIRING") + "</p>";
  html += "<p>NRF24L01: " + String(nrfConnected ? "CONNECTED" : "DISCONNECTED") + "</p>";
  html += "<p><a href='/data'>View Live JSON Stream: /data</a></p></body></html>";
  server.send(200, "text/html", html);
}

// ── setup() ───────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);

  // Initialize I2C Bus for BMP280 and MPU6050
  Wire.begin(21, 22);

  // 1. Initialize BMP280
  if (bmp.begin(0x76) || bmp.begin(0x77)) {
    bmpOnline = true;
    Serial.println(F("[OK] BMP280 Initialized."));
  } else {
    Serial.println(F("[WARN] BMP280 Not Detected."));
  }

  // 2. Initialize MPU6050
  if (mpu.begin()) {
    mpuOnline = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println(F("[OK] MPU6050 Initialized."));
  } else {
    Serial.println(F("[WARN] MPU6050 Not Detected."));
  }

  // 3. Initialize NRF24L01 on HSPI Bus
  hspi.begin(NRF_SCK, NRF_MISO, NRF_MOSI, NRF_CSN);
  delay(50);
  if (radio.begin(&hspi)) {
    radio.setChannel(76);
    radio.setPALevel(RF24_PA_HIGH);
    radio.setDataRate(RF24_1MBPS);
    if (radio.isChipConnected()) {
      nrfConnected = true;
      Serial.println(F("[OK] NRF24L01 Radio Connected."));
    }
  }

  // 4. Connect to Wi-Fi Hotspot
  Serial.print(F("Connecting to Wi-Fi SSID: "));
  Serial.println(ssid);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    digitalWrite(LED_PIN, HIGH); delay(150);
    digitalWrite(LED_PIN, LOW); delay(150);
    Serial.print('.');
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH);
    Serial.println();
    Serial.println(F("=================================================="));
    Serial.println(F("🔱 NAVAMESH ESP32 ONLINE ON STANDARD PORT 80"));
    Serial.print(F("📡 ESP32 IP ADDRESS: "));
    Serial.println(WiFi.localIP());
    Serial.print(F("🌐 TELEMETRY ENDPOINT: http://"));
    Serial.print(WiFi.localIP());
    Serial.println(F("/data"));
    Serial.println(F("=================================================="));
  } else {
    Serial.println(F("\n[!] Wi-Fi Connection Timeout. Streaming over Serial."));
  }

  // Setup Web Server Routes on default Port 80
  server.on("/", handleRoot);
  server.on("/data", handleDataRequest);
  server.begin();
}

// ── loop() ────────────────────────────────────────────────────────────────────
void loop() {
  // Handle incoming HTTP requests on port 80
  server.handleClient();

  // Emit Serial telemetry every 100ms
  unsigned long currentMillis = millis();
  if (currentMillis - lastReadTime >= 100) {
    lastReadTime = currentMillis;

    float bmpTemp = bmpOnline ? bmp.readTemperature() : 28.0;
    float bmpPres = bmpOnline ? bmp.readPressure() / 100.0F : 1013.25;
    float bmpAlt  = bmpOnline ? bmp.readAltitude(1013.25) : 0.0;

    sensors_event_t a, g, temp;
    float ax = 0, ay = 0, az = 1;
    if (mpuOnline) {
      mpu.getEvent(&a, &g, &temp);
      ax = a.acceleration.x / 9.80665F;
      ay = a.acceleration.y / 9.80665F;
      az = a.acceleration.z / 9.80665F;
      roll  = atan2(ay, az) * 180.0 / PI;
      pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;
      tilt  = sqrt(roll * roll + pitch * pitch);
    }

    // High-speed JSON stream over Serial
    Serial.print("{\"bmp\":{\"temperature\":");
    Serial.print(bmpTemp, 1);
    Serial.print(",\"pressure\":");
    Serial.print(bmpPres, 1);
    Serial.print(",\"altitude\":");
    Serial.print(bmpAlt, 1);
    Serial.print("},\"mpu\":{\"accel_x\":");
    Serial.print(ax, 2);
    Serial.print(",\"accel_y\":");
    Serial.print(ay, 2);
    Serial.print(",\"accel_z\":");
    Serial.print(az, 2);
    Serial.print(",\"roll\":");
    Serial.print(roll, 1);
    Serial.print(",\"pitch\":");
    Serial.print(pitch, 1);
    Serial.print(",\"tilt\":");
    Serial.print(tilt, 1);
    Serial.print("},\"nrf\":{\"status\":\"");
    Serial.print(nrfConnected ? "Active" : "Ready");
    Serial.print("\",\"channel\":76}}\n");
  }
}
