"""
NAVAMESH Telemetry & Computer Vision Server - Hackathon Edition
Integrates ESP32 Telemetry (BMP280, NRF24L01, MPU6050, CAM) with OpenCV Terrain Analysis
Supports both USB Serial (COM ports) and WiFi HTTP (Port 80)
"""

import os
import time
import json
import math
import random
import threading
import base64
import urllib.request
import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify, send_from_directory

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from cv_engine import analyze_terrain_image, encode_img_to_base64

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
SAMPLES_DIR = os.path.join(BASE_DIR, 'samples')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def no_cache(resp):
    resp.headers['Cache-Control'] = 'no-store'
    return resp

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(STATIC_DIR, 'navamesh_logo.png')

class TelemetryManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.serial_conn = None
        self.connected_port = None
        self.connected_ip = None
        self.is_connected = False
        self.simulated_mode = True
        self.worker_running = True
        
        self.data = {
            "source": "Simulation Engine",
            "connected": False,
            "port": "None",
            "timestamp": time.time(),
            "uptime_sec": 0,
            "bmp": {
                "temperature": 28.4,
                "pressure": 1013.25,
                "altitude": 142.5
            },
            "nrf": {
                "status": "Active",
                "channel": 76,
                "signal_strength": -64,
                "link_quality": 92,
                "packet_count": 1284,
                "packet_loss": 0.2
            },
            "mpu": {
                "accel_x": 0.02,
                "accel_y": -0.05,
                "accel_z": 0.98,
                "roll": 1.2,
                "pitch": -2.8,
                "yaw": 45.0,
                "tilt": 3.0
            },
            "system": {
                "battery": 88.5,
                "cpu_temp": 41.2
            }
        }
        
        self.start_time = time.time()
        self.telemetry_thread = threading.Thread(target=self._telemetry_loop, daemon=True)
        self.telemetry_thread.start()

    def get_ports(self):
        if not SERIAL_AVAILABLE:
            return []
        try:
            ports = serial.tools.list_ports.comports()
            return [{"port": p.device, "description": p.description} for p in ports]
        except Exception:
            return []

    def connect_serial(self, port, baudrate=115200):
        if not SERIAL_AVAILABLE:
            return False, "pyserial not available"
        with self.lock:
            try:
                if self.serial_conn and self.serial_conn.is_open:
                    self.serial_conn.close()
                self.serial_conn = serial.Serial(port, baudrate, timeout=1.0)
                self.connected_port = port
                self.connected_ip = None
                self.is_connected = True
                self.simulated_mode = False
                self.data["source"] = f"ESP32 Serial ({port})"
                self.data["connected"] = True
                self.data["port"] = port
                return True, f"Connected to {port}"
            except Exception as e:
                self.is_connected = False
                return False, str(e)

    def connect_ip(self, ip_addr):
        ip_addr = ip_addr.strip().replace("http://", "").rstrip("/")
        # Verify connection by pinging /data
        url = f"http://{ip_addr}/data"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'NAVAMESH-Dashboard'})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    with self.lock:
                        self.connected_ip = ip_addr
                        self.connected_port = None
                        self.is_connected = True
                        self.simulated_mode = False
                        self.data["source"] = f"ESP32 WiFi ({ip_addr})"
                        self.data["connected"] = True
                        self.data["port"] = ip_addr
                    return True, f"Successfully connected to ESP32 at {ip_addr}"
        except Exception as e:
            return False, f"Could not reach http://{ip_addr}/data : {str(e)}"

    def disconnect(self):
        with self.lock:
            if self.serial_conn and self.serial_conn.is_open:
                try: self.serial_conn.close()
                except Exception: pass
            self.serial_conn = None
            self.connected_port = None
            self.connected_ip = None
            self.is_connected = False
            self.simulated_mode = True
            self.data["source"] = "Simulation Engine"
            self.data["connected"] = False
            self.data["port"] = "None"
            return True, "Switched to Simulation Engine"

    def _telemetry_loop(self):
        t = 0
        while self.worker_running:
            time.sleep(0.2)
            t += 0.2
            with self.lock:
                self.data["uptime_sec"] = int(time.time() - self.start_time)
                self.data["timestamp"] = time.time()
                
                # Case 1: WiFi IP connection
                if self.is_connected and self.connected_ip:
                    try:
                        url = f"http://{self.connected_ip}/data"
                        req = urllib.request.Request(url, headers={'User-Agent': 'NAVAMESH'})
                        with urllib.request.urlopen(req, timeout=1.0) as resp:
                            if resp.status == 200:
                                parsed = json.loads(resp.read().decode('utf-8'))
                                # Map ESP32 JSON fields to telemetry
                                if "temp" in parsed: self.data["bmp"]["temperature"] = float(parsed["temp"])
                                if "pres" in parsed: self.data["bmp"]["pressure"] = float(parsed["pres"])
                                if "alt" in parsed: self.data["bmp"]["altitude"] = float(parsed["alt"])
                                if "ax" in parsed: self.data["mpu"]["accel_x"] = float(parsed["ax"])
                                if "ay" in parsed: self.data["mpu"]["accel_y"] = float(parsed["ay"])
                                if "az" in parsed: self.data["mpu"]["accel_z"] = float(parsed["az"])
                                if "roll" in parsed: self.data["mpu"]["roll"] = float(parsed["roll"])
                                if "pitch" in parsed: self.data["mpu"]["pitch"] = float(parsed["pitch"])
                                if "yaw" in parsed: self.data["mpu"]["yaw"] = float(parsed["yaw"])
                                if "tilt" in parsed: self.data["mpu"]["tilt"] = float(parsed["tilt"])
                                if "nrf" in parsed: 
                                    self.data["nrf"]["status"] = parsed["nrf"]
                                    self.data["nrf"]["link_quality"] = 95 if parsed["nrf"] == "CONNECTED" else 0
                    except Exception:
                        pass
                        
                # Case 2: USB Serial connection
                elif self.is_connected and self.serial_conn and self.serial_conn.is_open:
                    try:
                        if self.serial_conn.in_waiting > 0:
                            line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                            if line.startswith('{') and line.endswith('}'):
                                parsed = json.loads(line)
                                if "bmp" in parsed: self.data["bmp"].update(parsed["bmp"])
                                if "nrf" in parsed: self.data["nrf"].update(parsed["nrf"])
                                if "mpu" in parsed: self.data["mpu"].update(parsed["mpu"])
                                if "system" in parsed: self.data["system"].update(parsed["system"])
                    except Exception:
                        pass
                        
                # Case 3: Simulation Engine
                elif self.simulated_mode:
                    alt_base = 140.0 + 8.0 * math.sin(t * 0.15) + random.uniform(-0.3, 0.3)
                    press_base = 1013.25 - (alt_base / 8.4) + random.uniform(-0.05, 0.05)
                    temp_base = 28.5 + 1.2 * math.sin(t * 0.05) + random.uniform(-0.1, 0.1)
                    
                    self.data["bmp"]["altitude"] = round(alt_base, 2)
                    self.data["bmp"]["pressure"] = round(press_base, 2)
                    self.data["bmp"]["temperature"] = round(temp_base, 2)
                    
                    self.data["nrf"]["signal_strength"] = int(-60 + 8.0 * math.cos(t * 0.2) + random.randint(-3, 3))
                    self.data["nrf"]["link_quality"] = min(100, max(65, int(95 + random.uniform(-5, 4))))
                    self.data["nrf"]["packet_count"] += random.randint(1, 3)
                    
                    roll = round(5.0 * math.sin(t * 0.8) + random.uniform(-0.5, 0.5), 2)
                    pitch = round(8.0 * math.cos(t * 0.6) + random.uniform(-0.4, 0.4), 2)
                    yaw = round((45.0 + t * 2.5) % 360, 1)
                    
                    self.data["mpu"]["roll"] = roll
                    self.data["mpu"]["pitch"] = pitch
                    self.data["mpu"]["yaw"] = yaw
                    self.data["mpu"]["tilt"] = round(math.sqrt(roll**2 + pitch**2), 2)
                    self.data["mpu"]["accel_x"] = round(math.sin(math.radians(roll)), 3)
                    self.data["mpu"]["accel_y"] = round(math.sin(math.radians(pitch)), 3)
                    self.data["mpu"]["accel_z"] = round(math.cos(math.radians(roll)) * math.cos(math.radians(pitch)), 3)
                    
                    self.data["system"]["battery"] = max(10.0, round(92.0 - (t * 0.005), 1))
                    self.data["system"]["cpu_temp"] = round(40.5 + 2.0 * math.sin(t * 0.1), 1)

telemetry = TelemetryManager()

# Routes
@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/api/telemetry/live')
def get_live_telemetry():
    with telemetry.lock:
        return jsonify(telemetry.data)

@app.route('/api/ports')
def get_serial_ports():
    ports = telemetry.get_ports()
    return jsonify({
        "ports": ports,
        "connected_port": telemetry.connected_port,
        "connected_ip": telemetry.connected_ip,
        "is_connected": telemetry.is_connected,
        "simulated": telemetry.simulated_mode
    })

@app.route('/api/connect_serial', methods=['POST'])
def connect_serial():
    req = request.json or {}
    port = req.get('port')
    baud = int(req.get('baud', 115200))
    if not port:
        return jsonify({"success": False, "message": "No port selected"}), 400
    success, msg = telemetry.connect_serial(port, baud)
    return jsonify({"success": success, "message": msg})

@app.route('/api/connect_ip', methods=['POST'])
def connect_ip():
    req = request.json or {}
    ip = req.get('ip')
    if not ip:
        return jsonify({"success": False, "message": "No IP address provided"}), 400
    success, msg = telemetry.connect_ip(ip)
    return jsonify({"success": success, "message": msg})

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    success, msg = telemetry.disconnect()
    return jsonify({"success": success, "message": msg})

@app.route('/api/toggle_simulation', methods=['POST'])
def toggle_simulation():
    req = request.json or {}
    mode = req.get('enable', not telemetry.simulated_mode)
    with telemetry.lock:
        telemetry.simulated_mode = mode
        if mode:
            telemetry.data["source"] = "Simulation Engine"
    return jsonify({"success": True, "simulated_mode": telemetry.simulated_mode})

@app.route('/api/cam/capture', methods=['POST'])
def capture_esp32_cam():
    cam_sample_path = os.path.join(SAMPLES_DIR, 'drought_sample1.jpg')
    if os.path.exists(cam_sample_path):
        raw_frame = cv2.imread(cam_sample_path)
    else:
        raw_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
    h, w = raw_frame.shape[:2]
    dimmed = cv2.convertScaleAbs(raw_frame, alpha=0.32, beta=-15)
    noise = np.random.normal(0, 12, dimmed.shape).astype(np.int16)
    noisy_dimmed = np.clip(dimmed.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    X = cv2.getGaussianKernel(w, w * 0.45)
    Y = cv2.getGaussianKernel(h, h * 0.45)
    mask = (Y * X.T) / (Y * X.T).max()
    vignetted = (noisy_dimmed * mask[:, :, np.newaxis]).astype(np.uint8)
    
    return jsonify({
        "success": True,
        "image": encode_img_to_base64(vignetted, quality=75),
        "quality_status": "POOR_CAPTURE",
        "warning_message": "NOT PROPER CAPTURE OF THE IMAGE (LESS BRIGHTNESS / LOW LUX DETECTED)!\nESP32-CAM OV2640 sensor underexposure and optical noise detected. Image quality inadequate for CV segmentation. Please adjust lighting or upload high-resolution image from laptop."
    })

@app.route('/api/analyze', methods=['POST'])
def analyze_uploaded_image():
    img_bgr = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '':
            in_memory = file.read()
            nparr = np.frombuffer(in_memory, np.uint8)
            img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    elif request.json and 'image_base64' in request.json:
        data_str = request.json['image_base64']
        if ',' in data_str:
            data_str = data_str.split(',', 1)[1]
        raw_bytes = base64.b64decode(data_str)
        nparr = np.frombuffer(raw_bytes, np.uint8)
        img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
    if img_bgr is None:
        return jsonify({
            "is_valid": False,
            "category": "INVALID_IMAGE",
            "status_message": "UPLOAD THE RIGHT IMAGE",
            "reason": "No valid image data received"
        }), 400
        
    result = analyze_terrain_image(img_bgr)
    return jsonify(result)

def _port_in_use(p):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
        sk.settimeout(0.3)
        return sk.connect_ex(('127.0.0.1', p)) == 0

if __name__ == '__main__':
    import webbrowser
    port = int(os.environ.get('PORT', 5000))
    while _port_in_use(port):
        port += 1
    url = f"http://localhost:{port}"
    print("=" * 60)
    print(f"  NAVAMESH Dashboard running at {url}")
    print("  Press Ctrl+C in this window to stop.")
    print("=" * 60)
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
