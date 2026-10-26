/**
 * NAVAMESH ESP32 Telemetry & Vision Command Center - Hackathon Edition
 * Connects over WiFi HTTP (Port 80) or USB COM Serial
 */

document.addEventListener('DOMContentLoaded', () => {
    let currentAnalysisData = null;
    let altitudeChart = null;
    const maxHistoryPoints = 25;
    
    // Header Elements
    const hudClock = document.getElementById('hudClock');
    const hudUptime = document.getElementById('hudUptime');
    const connStatusBadge = document.getElementById('connStatusBadge');
    const connStatusText = document.getElementById('connStatusText');
    const espIpInput = document.getElementById('espIpInput');
    const btnConnectWifi = document.getElementById('btnConnectWifi');
    const portSelect = document.getElementById('portSelect');
    const btnScanPorts = document.getElementById('btnScanPorts');
    const btnConnectSerial = document.getElementById('btnConnectSerial');
    const btnDisconnectSerial = document.getElementById('btnDisconnectSerial');
    const simToggle = document.getElementById('simToggle');
    
    // Modal Elements
    const reconModal = document.getElementById('reconModal');
    const btnOpenReconModal = document.getElementById('btnOpenReconModal');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnOptionEsp32Cam = document.getElementById('btnOptionEsp32Cam');
    const btnOptionLaptop = document.getElementById('btnOptionLaptop');
    const sectionEsp32Cam = document.getElementById('sectionEsp32Cam');
    const sectionLaptop = document.getElementById('sectionLaptop');
    
    // Cam Elements
    const btnTriggerCamCapture = document.getElementById('btnTriggerCamCapture');
    const camCaptureResultArea = document.getElementById('camCaptureResultArea');
    const camCapturedImg = document.getElementById('camCapturedImg');
    const camWarningText = document.getElementById('camWarningText');
    
    // Laptop Upload Elements
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const cvLoadingSpinner = document.getElementById('cvLoadingSpinner');
    const invalidImageAlert = document.getElementById('invalidImageAlert');
    const invalidReasonText = document.getElementById('invalidReasonText');
    const cvResultsContainer = document.getElementById('cvResultsContainer');
    
    // CV Results Elements
    const categoryBadge = document.getElementById('categoryBadge');
    const resWaterPct = document.getElementById('resWaterPct');
    const resDroughtPct = document.getElementById('resDroughtPct');
    const resSkyPct = document.getElementById('resSkyPct');
    const resSkyPctText = document.getElementById('resSkyPctText');
    const resStatusMessage = document.getElementById('resStatusMessage');
    const analysisDisplayImg = document.getElementById('analysisDisplayImg');
    const viewTabs = document.querySelectorAll('.view-tab');

    // Canvas Artificial Horizon
    const horizonCanvas = document.getElementById('horizonCanvas');
    const horizonCtx = horizonCanvas ? horizonCanvas.getContext('2d') : null;

    function initChart() {
        const ctx = document.getElementById('altitudeChart').getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 110);
        gradient.addColorStop(0, 'rgba(0, 255, 85, 0.35)');
        gradient.addColorStop(1, 'rgba(0, 255, 85, 0.0)');

        altitudeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array(maxHistoryPoints).fill(''),
                datasets: [{
                    label: 'Altitude (m)',
                    data: Array(maxHistoryPoints).fill(140),
                    borderColor: '#10f543',
                    borderWidth: 2,
                    backgroundColor: gradient,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: { display: false },
                    y: {
                        grid: { color: 'rgba(0, 255, 85, 0.08)' },
                        ticks: { color: '#8aa992', font: { family: 'Share Tech Mono', size: 9 } }
                    }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    function drawArtificialHorizon(rollDeg, pitchDeg) {
        if (!horizonCtx) return;
        const w = horizonCanvas.width;
        const h = horizonCanvas.height;
        const cx = w / 2;
        const cy = h / 2;
        const r = w / 2 - 4;

        horizonCtx.clearRect(0, 0, w, h);
        horizonCtx.save();
        horizonCtx.beginPath();
        horizonCtx.arc(cx, cy, r, 0, Math.PI * 2);
        horizonCtx.clip();

        horizonCtx.translate(cx, cy);
        horizonCtx.rotate((-rollDeg * Math.PI) / 180);

        const pitchOffset = Math.min(Math.max(pitchDeg * 2.2, -r + 10), r - 10);

        // Ground
        horizonCtx.fillStyle = '#06170a';
        horizonCtx.fillRect(-w, pitchOffset, w * 2, h);

        // Sky
        horizonCtx.fillStyle = '#030a10';
        horizonCtx.fillRect(-w, -h + pitchOffset, w * 2, h);

        // Horizon Line
        horizonCtx.strokeStyle = '#00ff55';
        horizonCtx.lineWidth = 2;
        horizonCtx.beginPath();
        horizonCtx.moveTo(-w, pitchOffset);
        horizonCtx.lineTo(w, pitchOffset);
        horizonCtx.stroke();

        // Pitch ladder
        horizonCtx.strokeStyle = 'rgba(0, 255, 85, 0.4)';
        horizonCtx.lineWidth = 1;
        for (let p = -30; p <= 30; p += 10) {
            if (p === 0) continue;
            const y = pitchOffset - p * 2.2;
            const lineLen = Math.abs(p) % 20 === 0 ? 28 : 16;
            horizonCtx.beginPath();
            horizonCtx.moveTo(-lineLen, y);
            horizonCtx.lineTo(lineLen, y);
            horizonCtx.stroke();
        }
        horizonCtx.restore();

        // Aircraft Reticle
        horizonCtx.save();
        horizonCtx.translate(cx, cy);
        horizonCtx.strokeStyle = '#10f543';
        horizonCtx.lineWidth = 2.5;
        horizonCtx.fillStyle = '#ff9100';
        horizonCtx.beginPath();
        horizonCtx.arc(0, 0, 3, 0, Math.PI * 2);
        horizonCtx.fill();
        horizonCtx.beginPath();
        horizonCtx.moveTo(-32, 0);
        horizonCtx.lineTo(-12, 0);
        horizonCtx.moveTo(12, 0);
        horizonCtx.lineTo(32, 0);
        horizonCtx.stroke();
        horizonCtx.restore();

        // Outer Ring
        horizonCtx.strokeStyle = 'rgba(0, 255, 85, 0.6)';
        horizonCtx.lineWidth = 2;
        horizonCtx.beginPath();
        horizonCtx.arc(cx, cy, r, 0, Math.PI * 2);
        horizonCtx.stroke();
    }

    async function fetchTelemetry() {
        try {
            const resp = await fetch('/api/telemetry/live');
            if (!resp.ok) return;
            const d = await resp.json();

            hudUptime.textContent = `${d.uptime_sec}s`;
            if (d.connected) {
                connStatusBadge.className = 'telemetry-badge connected';
                connStatusText.textContent = `ESP32 LIVE (${d.port})`;
            } else {
                connStatusBadge.className = 'telemetry-badge';
                connStatusText.textContent = d.source.toUpperCase();
            }

            document.getElementById('bmpPressure').textContent = d.bmp.pressure.toFixed(1);
            document.getElementById('bmpAltitude').textContent = d.bmp.altitude.toFixed(1);
            document.getElementById('bmpTemp').textContent = d.bmp.temperature.toFixed(1);
            
            if (altitudeChart) {
                const dataset = altitudeChart.data.datasets[0].data;
                dataset.shift();
                dataset.push(d.bmp.altitude);
                altitudeChart.update();
            }

            document.getElementById('mpuAx').textContent = d.mpu.accel_x.toFixed(2);
            document.getElementById('mpuAy').textContent = d.mpu.accel_y.toFixed(2);
            document.getElementById('mpuAz').textContent = d.mpu.accel_z.toFixed(2);
            drawArtificialHorizon(d.mpu.roll, d.mpu.pitch);

            document.getElementById('nrfSignal').textContent = d.nrf.signal_strength;
            document.getElementById('nrfLink').textContent = d.nrf.link_quality;
            document.getElementById('nrfChannel').textContent = `CH ${d.nrf.channel}`;
            document.getElementById('nrfPackets').textContent = d.nrf.packet_count;
            document.getElementById('nrfLoss').textContent = `${d.nrf.packet_loss}%`;
            document.getElementById('nrfLinkBar').style.width = `${d.nrf.link_quality}%`;

            const rssi = d.nrf.signal_strength;
            const bars = document.querySelectorAll('#rfSignalBars .bar');
            let activeBars = 1;
            if (rssi > -60) activeBars = 5;
            else if (rssi > -70) activeBars = 4;
            else if (rssi > -80) activeBars = 3;
            else if (rssi > -90) activeBars = 2;
            bars.forEach((b, idx) => {
                b.className = idx < activeBars ? 'bar active' : 'bar';
            });

            document.getElementById('sysBattery').textContent = d.system.battery.toFixed(1);
            document.getElementById('sysBatteryBar').style.width = `${d.system.battery}%`;
            document.getElementById('sysCpuTemp').textContent = d.system.cpu_temp.toFixed(1);
            document.getElementById('sysSource').textContent = d.source;
            document.getElementById('sysPort').textContent = d.port || 'None';

        } catch (err) {
            console.error('Telemetry fetch error:', err);
        }
    }

    // Connect via WiFi IP
    btnConnectWifi.addEventListener('click', async () => {
        const ip = espIpInput.value.trim();
        if (!ip) {
            alert('Please enter your ESP32 IP address (from Serial Monitor).');
            return;
        }
        btnConnectWifi.textContent = 'LINKING...';
        try {
            const resp = await fetch('/api/connect_ip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip: ip })
            });
            const res = await resp.json();
            btnConnectWifi.textContent = 'IP LINK';
            if (res.success) {
                btnConnectWifi.style.display = 'none';
                btnConnectSerial.style.display = 'none';
                btnDisconnectSerial.style.display = 'inline-flex';
                simToggle.checked = false;
            } else {
                alert(res.message);
            }
        } catch (e) {
            btnConnectWifi.textContent = 'IP LINK';
            alert('Failed to connect to ESP32 IP.');
        }
    });

    // Scan COM ports
    async function scanSerialPorts() {
        try {
            portSelect.innerHTML = '<option value="">Scanning...</option>';
            const resp = await fetch('/api/ports');
            const data = await resp.json();
            portSelect.innerHTML = '';

            if (data.ports.length === 0) {
                portSelect.innerHTML = '<option value="">No COM Ports Detected</option>';
            } else {
                data.ports.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.port;
                    opt.textContent = `${p.port} (${p.description})`;
                    if (data.connected_port === p.port) opt.selected = true;
                    portSelect.appendChild(opt);
                });
            }

            if (data.is_connected) {
                btnConnectSerial.style.display = 'none';
                btnConnectWifi.style.display = 'none';
                btnDisconnectSerial.style.display = 'inline-flex';
            } else {
                btnConnectSerial.style.display = 'inline-flex';
                btnConnectWifi.style.display = 'inline-flex';
                btnDisconnectSerial.style.display = 'none';
            }
        } catch (e) {
            console.error('Scan ports error:', e);
        }
    }

    btnConnectSerial.addEventListener('click', async () => {
        const port = portSelect.value;
        if (!port) {
            alert('Please select a valid COM port.');
            return;
        }
        btnConnectSerial.textContent = 'CONNECTING...';
        const resp = await fetch('/api/connect_serial', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ port: port, baud: 115200 })
        });
        const res = await resp.json();
        btnConnectSerial.textContent = 'COM LINK';
        if (res.success) {
            btnConnectSerial.style.display = 'none';
            btnConnectWifi.style.display = 'none';
            btnDisconnectSerial.style.display = 'inline-flex';
            simToggle.checked = false;
        } else {
            alert(res.message);
        }
    });

    btnDisconnectSerial.addEventListener('click', async () => {
        await fetch('/api/disconnect', { method: 'POST' });
        btnConnectSerial.style.display = 'inline-flex';
        btnConnectWifi.style.display = 'inline-flex';
        btnDisconnectSerial.style.display = 'none';
        simToggle.checked = true;
    });

    btnScanPorts.addEventListener('click', scanSerialPorts);

    simToggle.addEventListener('change', async () => {
        await fetch('/api/toggle_simulation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enable: simToggle.checked })
        });
    });

    setInterval(() => {
        const now = new Date();
        hudClock.textContent = now.toTimeString().split(' ')[0];
    }, 1000);

    // Modal Controller
    btnOpenReconModal.addEventListener('click', () => reconModal.classList.add('active'));
    btnCloseModal.addEventListener('click', () => reconModal.classList.remove('active'));

    btnOptionEsp32Cam.addEventListener('click', () => {
        btnOptionEsp32Cam.classList.add('active');
        btnOptionLaptop.classList.remove('active');
        sectionEsp32Cam.style.display = 'flex';
        sectionLaptop.style.display = 'none';
    });

    btnOptionLaptop.addEventListener('click', () => {
        btnOptionLaptop.classList.add('active');
        btnOptionEsp32Cam.classList.remove('active');
        sectionLaptop.style.display = 'flex';
        sectionEsp32Cam.style.display = 'none';
    });

    // ESP32 Cam Capture
    btnTriggerCamCapture.addEventListener('click', async () => {
        btnTriggerCamCapture.textContent = 'CAPTURING RAW OPTICAL FRAME...';
        btnTriggerCamCapture.disabled = true;

        try {
            const resp = await fetch('/api/cam/capture', { method: 'POST' });
            const data = await resp.json();

            camCapturedImg.src = data.image;
            camCaptureResultArea.style.display = 'flex';
            if (data.warning_message) {
                camWarningText.textContent = data.warning_message;
            }
        } catch (err) {
            console.error('Camera capture error:', err);
        } finally {
            btnTriggerCamCapture.textContent = '⚡ CAPTURE FRAME FROM ESP32-CAM';
            btnTriggerCamCapture.disabled = false;
        }
    });

    // Laptop File Upload Handler
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) processUploadFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) processUploadFile(fileInput.files[0]);
    });

    async function processUploadFile(file) {
        const formData = new FormData();
        formData.append('image', file);

        cvLoadingSpinner.style.display = 'flex';
        invalidImageAlert.style.display = 'none';
        cvResultsContainer.style.display = 'none';

        try {
            const resp = await fetch('/api/analyze', { method: 'POST', body: formData });
            const result = await resp.json();
            renderAnalysisResult(result);
        } catch (err) {
            showInvalidImageAlert("Error processing image file.");
        } finally {
            cvLoadingSpinner.style.display = 'none';
        }
    }

    function renderAnalysisResult(res) {
        currentAnalysisData = res;

        // Check if invalid per user rule:
        if (!res.is_valid || res.category === 'INVALID_IMAGE') {
            showInvalidImageAlert(res.reason || "This image does not contain confirmed Drought Desiccation cracks or Flood Inundation surface water.");
            return;
        }

        invalidImageAlert.style.display = 'none';
        cvResultsContainer.style.display = 'flex';

        if (res.category === 'DROUGHT') {
            categoryBadge.className = 'disaster-badge drought';
            categoryBadge.textContent = '🌵 DROUGHT DETECTED';
        } else if (res.category.includes('FLOOD')) {
            categoryBadge.className = 'disaster-badge flood';
            categoryBadge.textContent = '🌊 HEAVY RAINFALL / FLOOD DETECTED';
        }

        resWaterPct.textContent = `${res.water_coverage_pct}%`;
        resDroughtPct.textContent = `${res.drought_coverage_pct}%`;
        resSkyPct.textContent = `${res.sky_coverage_pct}%`;
        resSkyPctText.textContent = `${res.sky_coverage_pct}%`;
        resStatusMessage.textContent = res.status_message;

        setActiveViewTab('side_by_side');
    }

    function showInvalidImageAlert(reason) {
        cvResultsContainer.style.display = 'none';
        invalidImageAlert.style.display = 'flex';
        invalidReasonText.textContent = reason;
    }

    viewTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const viewType = tab.getAttribute('data-view');
            setActiveViewTab(viewType);
        });
    });

    function setActiveViewTab(viewType) {
        if (!currentAnalysisData) return;
        viewTabs.forEach(t => {
            if (t.getAttribute('data-view') === viewType) t.classList.add('active');
            else t.classList.remove('active');
        });

        if (viewType === 'side_by_side' && currentAnalysisData.side_by_side_image) {
            analysisDisplayImg.src = currentAnalysisData.side_by_side_image;
        } else if (viewType === 'overlay' && currentAnalysisData.overlay_image) {
            analysisDisplayImg.src = currentAnalysisData.overlay_image;
        } else if (viewType === 'mask' && currentAnalysisData.binary_mask_image) {
            analysisDisplayImg.src = currentAnalysisData.binary_mask_image;
        }
    }

    initChart();
    scanSerialPorts();
    setInterval(fetchTelemetry, 300);
});
