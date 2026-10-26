# NAVAMESH (EST. 2025) — ESP32 Telemetry & Vision Recon Command Center

An advanced telemetry dashboard and computer vision system built for **ESP32** hardware integration and terrain disaster intelligence (Drought & Heavy Rainfall/Flood).

---

## 🔱 Aesthetic & Design Theme
Designed from the **NAVAMESH** brand signature:
- **Primary Colors:** Deep Carbon Pitch-Black (`#020503`, `#050d07`) and Electric Neon Cyber Emerald / Lime Green (`#00ff55`, `#10f543`, `#39ff14`).
- **Tactical Accents:** Aqua Cyan (`#00e5ff`) for water inundation, Glowing Amber (`#ff9100`) for drought desiccation, Alert Red (`#ff1744`) for non-target rejection.
- **HUD Elements:** Tactical artificial horizon, live telemetry waveforms, glowing neon badges, and glassmorphic panels.

---

## 🚀 Key Features

### 1. Real-Life ESP32 Telemetry Integration
- **BMP Sensor (BMP280 / BMP180):** Live Barometric Pressure ($hPa$), Altitude ($m$), and Ambient Temperature ($°C$).
- **NRF Module (NRF24L01+ 2.4 GHz):** Signal Strength ($RSSI$ in $dBm$), Link Quality ($\%$), RF Channel ($CH\ 76$), and Packet loss tracking.
- **MPU Sensor (MPU6050):** 6-Axis motion ($Ax, Ay, Az$), Gyro ($Roll, Pitch, Yaw$), and an interactive **Canvas 3D Artificial Horizon**.
- **Serial Port Auto-Detector:** Scans USB/COM ports (CH340, CP2102, FTDI), one-click Connect / Disconnect at 115200 baud.
- **Fail-Safe Simulator Mode:** Built-in high-fidelity physics simulator allows complete dashboard testing even when the ESP32 is unplugged.

---

### 2. Dual-Option Recon Workflow (As Specified)
Clicking **"OPEN IMAGE RECON & CAPTURE SUITE"** gives you two operational pathways:

1. **Option 1: Upload Image from ESP32-CAM**
   - Triggers optical capture from the onboard OV2640 camera module.
   - Accurately assesses sensor exposure and renders the captured frame along with the required quality flag:
     > **⚠️ NOT PROPER CAPTURE OF THE IMAGE (LESS BRIGHTNESS / LOW LUX DETECTED)!**  
     > *ESP32-CAM OV2640 sensor recorded low illumination. Image clarity is suboptimal for precision CV segmentation. Please adjust lighting or upload high-resolution image from laptop.*

2. **Option 2: Upload Image from Laptop (Precision OpenCV Engine)**
   - Drag-and-drop or file upload for high-resolution images.
   - Includes 5 quick-verification buttons trained on your provided sample datasets:
     - 🌵 **Drought Sample #1**
     - 🌵 **Drought Sample #2**
     - 🌊 **Flood Sample #1**
     - 🌊 **Flood Sample #2**
     - 🚫 **Non-Target Test (Logo / Graphics)**

---

### 3. Precision OpenCV Segmentation & Sky Exclusion
- **The Sky Negative Factor Solution:**
  Blue or overcast skies often trick naive classifiers into detecting water or drought. The NAVAMESH CV Engine computes an algorithmic **Sky Horizon Mask** starting from the upper boundary down to the terrain plane, strictly subtracting all sky pixels from the terrain calculations.
- **Drought Segmentation:**
  Uses morphological black-hat transforms and warm soil color filtering to identify the interlocking polygonal fissure network across parched earth, highlighting cracked ground with an amber/orange glow overlay.
- **Flood / Water Segmentation:**
  Identifies expansive low-gradient surface water bodies, separates them from vegetation and rooftops, and highlights inundated zones in electric cyan.
- **Strict Quality Gate ("UPLOAD THE RIGHT IMAGE"):**
  If an image is uploaded that does not meet the verified criteria for drought desiccation or flood inundation (e.g. logos, documents, interior rooms, portraits), the dashboard blocks false positives and displays:
  > **🛑 UPLOAD THE RIGHT IMAGE**

---

## 🛠️ Project Structure

```
navamesh_telemetry_cv_dashboard/
├── server.py              # Flask Backend with Serial COM & CV Endpoints
├── cv_engine.py           # Core OpenCV Engine (Sky Exclusion, Crack & Water Masks)
├── static/
│   ├── index.html         # Cyberpunk NAVAMESH HUD Dashboard
│   ├── style.css          # Neon Green & Pitch Black Visual Theme
│   ├── app.js            # Real-Time Telemetry & Canvas Horizon Controller
│   └── navamesh_logo.png  # Brand Logo
├── firmware/
│   └── navamesh_telemetry_hub_clean/
│       └── navamesh_telemetry_hub_clean.ino  # ESP32 sketch (open this folder in Arduino IDE)
├── samples/               # Pre-loaded training images for one-click testing
└── README.md
```

---

## ⚡ Quick Start

### 1. Launch the Server
Double-click **`RUN_DASHBOARD.bat`**. It installs missing packages on first run, starts the server and opens the dashboard in your browser automatically (default `http://localhost:5000`, next free port if busy).

Manual alternative:
```bash
pip install -r requirements.txt
python server.py
```

### 2. Flashing the ESP32 Firmware
1. Open `firmware/navamesh_telemetry_hub_clean/navamesh_telemetry_hub_clean.ino` in Arduino IDE.
2. Install the required libraries via the Arduino Library Manager:
   - `Adafruit BMP280 Library`
   - `Adafruit MPU6050`
   - `RF24` by TMRh20
3. Connect your ESP32 via USB and select the COM port.
4. Click **Upload**.
5. In the NAVAMESH Dashboard, click **SCAN**, choose your COM port, and click **CONNECT**!

### 3. Linking the dashboard to the ESP32 over Wi-Fi
1. Put the laptop and the ESP32 on the same hotspot (`Kanha`).
2. Find the ESP32 IP in your phone's hotspot device list (or `arp -a` in CMD).
3. In the dashboard, type that IP into the **ESP32 IP** box and click **IP LINK**.
4. The ESP32 Serial Monitor (115200) prints `200` while the dashboard is connected and `0` when it is not.
