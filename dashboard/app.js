/**
 * ==============================================================================
 * TINYML SMART PARKING DASHBOARD - APPLICATION CONTROLLER
 * Supports:
 * 1. Interactive 4-Phase Diorama Simulation (Matching Exact Project Specs)
 * 2. Live MQTT WebSocket Client for real ESP32-CAM telemetry
 * 3. 64x64 Grayscale Frame Rendering & Scanning Animation
 * 4. Energy & Sensor Telemetry Visualizer
 * ==============================================================================
 */

// ------------------------------------------------------------------------------
// GLOBAL APPLICATION STATE
// ------------------------------------------------------------------------------
const state = {
  currentPhase: 1,
  isAutoPlaying: false,
  autoPlayTimer: null,
  mode: 'sim', // 'sim' | 'live'
  
  // Telemetry
  spot1: {
    status: 'VACANT',
    distance: 48.2,
    confidence: 0.05,
    latency: 38,
    current_mA: 14.5,
    lastReason: 'STANDBY_EMPTY'
  },
  
  // MQTT
  mqttClient: null,
  mqttConnected: false
};

// DOM References
const elements = {
  // Phase Buttons
  btnPhase1: document.getElementById('btn-phase-1'),
  btnPhase2: document.getElementById('btn-phase-2'),
  btnPhase3: document.getElementById('btn-phase-3'),
  btnPhase4: document.getElementById('btn-phase-4'),
  btnAutoDemo: document.getElementById('btn-auto-demo'),
  btnResetDemo: document.getElementById('btn-reset-demo'),
  
  // Mode & Status
  btnModeSim: document.getElementById('btn-mode-sim'),
  btnModeLive: document.getElementById('btn-mode-live'),
  mqttDot: document.getElementById('mqtt-dot'),
  mqttStatusText: document.getElementById('mqtt-status-text'),
  
  // Spot 1 Visuals
  spot1El: document.getElementById('spot-1'),
  spot1StateText: document.getElementById('slot-state-text-1'),
  objectVisual1: document.getElementById('object-visual-1'),
  spotDist1: document.getElementById('spot-dist-1'),
  spotProb1: document.getElementById('spot-prob-1'),
  
  // Telemetry
  telemetryDistance: document.getElementById('telemetry-distance'),
  distanceBar: document.getElementById('distance-bar'),
  distanceHint: document.getElementById('distance-hint'),
  telemetryCurrent: document.getElementById('telemetry-current'),
  powerTag: document.getElementById('power-tag'),
  
  // AI Inspector
  cameraCanvas: document.getElementById('cameraCanvas'),
  camStatusTag: document.getElementById('cam-status-tag'),
  aiBoundingBox: document.getElementById('ai-bounding-box'),
  aiProbVal: document.getElementById('ai-prob-val'),
  aiClassBadge: document.getElementById('ai-class-badge'),
  aiGaugeFill: document.getElementById('ai-gauge-fill'),
  aiLatencyVal: document.getElementById('ai-latency-val'),
  
  // Logs
  logContainer: document.getElementById('log-container'),
  btnClearLogs: document.getElementById('btn-clear-logs'),
  
  // MQTT Config
  toggleMqttConfig: document.getElementById('toggle-mqtt-config'),
  mqttConfigBody: document.getElementById('mqtt-config-body'),
  cfgMqttHost: document.getElementById('cfg-mqtt-host'),
  cfgMqttTopic: document.getElementById('cfg-mqtt-topic'),
  btnConnectMqtt: document.getElementById('btn-connect-mqtt')
};

// ------------------------------------------------------------------------------
// CANVAS 64x64 RENDERER (Simulates Camera OV2640 Frame)
// ------------------------------------------------------------------------------
const ctx = elements.cameraCanvas.getContext('2d');

function renderCanvasFrame(type) {
  // Clear
  ctx.fillStyle = '#22272e';
  ctx.fillRect(0, 0, 64, 64);
  
  // Draw floor noise
  for (let i = 0; i < 64; i += 2) {
    for (let j = 0; j < 64; j += 2) {
      const shade = Math.floor(30 + Math.random() * 15);
      ctx.fillStyle = `rgb(${shade},${shade},${shade})`;
      ctx.fillRect(i, j, 2, 2);
    }
  }
  
  // Draw parking stall line marks
  ctx.fillStyle = '#7a8594';
  ctx.fillRect(4, 0, 2, 64);
  ctx.fillRect(58, 0, 2, 64);

  if (type === 'car') {
    // Render Toy Car (Chữ nhật đối xứng có mui xe, đèn)
    ctx.save();
    ctx.translate(32, 32);
    ctx.rotate(0.08); // Slight angle
    
    // Wheels
    ctx.fillStyle = '#111';
    ctx.fillRect(-12, -16, 4, 7);
    ctx.fillRect(8, -16, 4, 7);
    ctx.fillRect(-12, 9, 4, 7);
    ctx.fillRect(8, 9, 4, 7);

    // Car Body
    ctx.fillStyle = '#b8c2cc';
    ctx.fillRect(-10, -18, 20, 36);

    // Windshield & Roof
    ctx.fillStyle = '#475569';
    ctx.fillRect(-7, -8, 14, 16);

    // Headlights
    ctx.fillStyle = '#f8fafc';
    ctx.fillRect(-7, 16, 4, 2);
    ctx.fillRect(3, 16, 4, 2);
    ctx.restore();

  } else if (type === 'human') {
    // Render Hand / Human Silhouette (Lòng bàn tay và các ngón bất đối xứng)
    ctx.save();
    ctx.translate(32, 32);
    
    // Palm
    ctx.fillStyle = '#a1a1aa';
    ctx.beginPath();
    ctx.ellipse(0, 2, 10, 8, 0, 0, Math.PI * 2);
    ctx.fill();

    // Fingers
    ctx.fillRect(-9, -14, 3, 12);
    ctx.fillRect(-4, -17, 3, 15);
    ctx.fillRect(1, -16, 3, 14);
    ctx.fillRect(6, -12, 3, 10);
    ctx.restore();

  } else {
    // Empty Spot: Draw subtle floor pattern
    ctx.fillStyle = '#334155';
    ctx.fillRect(28, 28, 8, 8);
  }
}

// ------------------------------------------------------------------------------
// REAL-TIME EVENT LOGGING
// ------------------------------------------------------------------------------
function appendLog(message, badgeText, badgeClass = 'log-badge-green', borderClass = 'log-green') {
  const now = new Date();
  const timeStr = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');

  const item = document.createElement('div');
  item.className = `log-entry ${borderClass}`;
  item.innerHTML = `
    <span class="log-timestamp">[${timeStr}]</span>
    <span class="log-badge-inline ${badgeClass}">${badgeText}</span>
    <span>${message}</span>
  `;

  elements.logContainer.prepend(item);

  // Keep log size <= 50 entries
  while (elements.logContainer.children.length > 50) {
    elements.logContainer.removeChild(elements.logContainer.lastChild);
  }
}

// ------------------------------------------------------------------------------
// 4-PHASE SIMULATION HANDLERS
// ------------------------------------------------------------------------------
function setPhase(phaseNum) {
  state.currentPhase = phaseNum;

  // Update button active styles
  [elements.btnPhase1, elements.btnPhase2, elements.btnPhase3, elements.btnPhase4].forEach((btn, idx) => {
    if (idx + 1 === phaseNum) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });

  switch (phaseNum) {
    case 1:
      runPhase1Baseline();
      break;
    case 2:
      runPhase2HumanNoise();
      break;
    case 3:
      runPhase3CarArrival();
      break;
    case 4:
      runPhase4CarDeparture();
      break;
  }
}

// PHA 1: BASELINE (Ô trống, hệ thống ngủ, dashboard màu Xanh)
function runPhase1Baseline() {
  state.spot1.status = 'VACANT';
  state.spot1.distance = 48.2;
  state.spot1.confidence = 0.04;
  state.spot1.current_mA = 14.5;
  state.spot1.lastReason = 'IDLE_VACANT';

  // UI updates
  elements.spot1El.className = 'parking-slot vacant';
  elements.spot1StateText.textContent = 'TRỐNG (VACANT)';
  elements.objectVisual1.innerHTML = `<div class="empty-placeholder">Ô TRỐNG</div>`;
  elements.spotDist1.textContent = '48.2 cm';
  elements.spotProb1.textContent = '0.04';

  elements.telemetryDistance.innerHTML = `48.2 <span class="unit">cm</span>`;
  elements.distanceBar.style.width = '85%';
  elements.distanceBar.style.background = '#38bdf8';
  elements.distanceHint.textContent = 'Vùng an toàn (> 15cm)';

  elements.telemetryCurrent.innerHTML = `14.5 <span class="unit">mA</span>`;
  elements.powerTag.textContent = '💤 Chế độ Chờ (Standby)';
  elements.powerTag.style.color = '#10b981';

  elements.camStatusTag.textContent = 'STANDBY (SLEEP)';
  elements.camStatusTag.style.background = '#334155';
  elements.aiBoundingBox.classList.remove('active');

  elements.aiProbVal.textContent = '0.04';
  elements.aiProbVal.style.color = '#38bdf8';
  elements.aiClassBadge.className = 'classification-badge badge-human';
  elements.aiClassBadge.textContent = 'TRỐNG / KHÔNG CÓ XE';
  elements.aiGaugeFill.style.width = '4%';
  elements.aiLatencyVal.textContent = '-- ms';

  renderCanvasFrame('empty');

  appendLog('Ô đỗ đang TRỐNG. ESP32-CAM ở trạng thái ngủ, chỉ đọc cảm biến định kỳ.', 'BASELINE', 'log-badge-green', 'log-green');
}

// PHA 2: Mô phỏng vật cản không phải xe; CNN trả điểm có xe dưới ngưỡng.
function runPhase2HumanNoise() {
  appendLog('Cảm biến phát hiện vật thể ở cự ly 11.2 cm (< 15cm). ĐÁNH THỨC CAMERA & AI!', 'WAKE SENSOR', 'log-badge-amber', 'log-amber');

  // Bước 1: Đánh thức Camera & chạy AI (Evaluating)
  elements.spot1El.className = 'parking-slot evaluating';
  elements.camStatusTag.textContent = 'CAMERA WAKE & SCAN';
  elements.camStatusTag.style.background = '#06b6d4';
  elements.telemetryCurrent.innerHTML = `178.2 <span class="unit">mA</span>`;
  elements.powerTag.textContent = '⚡ Camera & AI Đang Xử Lý';
  elements.powerTag.style.color = '#06b6d4';

  renderCanvasFrame('human');
  elements.aiBoundingBox.classList.add('active');

  setTimeout(() => {
    // Bước 2: Mô phỏng nhãn 0, không có xe (điểm 0.14 < 0.75).
    state.spot1.status = 'VACANT';
    state.spot1.distance = 11.2;
    state.spot1.confidence = 0.14;
    state.spot1.current_mA = 15.0;

    elements.spot1El.className = 'parking-slot vacant';
    elements.spot1StateText.textContent = 'TRỐNG (VACANT)';
    elements.objectVisual1.innerHTML = `<div class="human-graphic">🖐️</div>`;
    elements.spotDist1.textContent = '11.2 cm';
    elements.spotProb1.textContent = '0.14';

    elements.telemetryDistance.innerHTML = `11.2 <span class="unit">cm</span>`;
    elements.distanceBar.style.width = '24%';
    elements.distanceBar.style.background = '#f59e0b';
    elements.distanceHint.textContent = 'Vật cản gần (< 15cm)';

    elements.telemetryCurrent.innerHTML = `15.0 <span class="unit">mA</span>`;
    elements.powerTag.textContent = '💤 Trở lại Chế độ Chờ';
    elements.powerTag.style.color = '#10b981';

    elements.camStatusTag.textContent = 'STANDBY';
    elements.camStatusTag.style.background = '#334155';
    elements.aiBoundingBox.classList.remove('active');

    elements.aiProbVal.textContent = '0.14';
    elements.aiProbVal.style.color = '#f59e0b';
    elements.aiClassBadge.className = 'classification-badge badge-human';
    elements.aiClassBadge.textContent = 'KHÔNG CÓ XE (0)';
    elements.aiGaugeFill.style.width = '14%';
    elements.aiLatencyVal.textContent = '41 ms';

    appendLog('[Mô phỏng] CNN: KHÔNG CÓ XE (điểm có xe 14% < 75%). Giữ màu XANH.', 'NO CAR', 'log-badge-amber', 'log-amber');
  }, 700);
}

// PHA 3: ĐỖ XE Ô TÔ (Cảm biến nhận < 15cm, bật camera, CNN = Xe > 0.75 -> Chuyển ĐỎ)
function runPhase3CarArrival() {
  appendLog('Cảm biến phát hiện vật thể ở cự ly 8.4 cm (< 15cm). ĐÁNH THỨC CAMERA & AI!', 'WAKE SENSOR', 'log-badge-cyan', 'log-cyan');

  // Đang quét
  elements.spot1El.className = 'parking-slot evaluating';
  elements.camStatusTag.textContent = 'CAMERA WAKE & SCAN';
  elements.camStatusTag.style.background = '#06b6d4';
  elements.telemetryCurrent.innerHTML = `182.5 <span class="unit">mA</span>`;
  elements.powerTag.textContent = '⚡ Camera & AI Đang Xử Lý';
  elements.powerTag.style.color = '#06b6d4';

  renderCanvasFrame('car');
  elements.aiBoundingBox.classList.add('active');

  setTimeout(() => {
    // AI kết luận Xe (Confidence 0.94 >= 0.75)
    state.spot1.status = 'OCCUPIED';
    state.spot1.distance = 8.4;
    state.spot1.confidence = 0.94;
    state.spot1.current_mA = 16.2;

    elements.spot1El.className = 'parking-slot occupied';
    elements.spot1StateText.textContent = 'CÓ XE (OCCUPIED)';
    elements.objectVisual1.innerHTML = `<div class="car-graphic">CAR 01</div>`;
    elements.spotDist1.textContent = '8.4 cm';
    elements.spotProb1.textContent = '0.94';

    elements.telemetryDistance.innerHTML = `8.4 <span class="unit">cm</span>`;
    elements.distanceBar.style.width = '18%';
    elements.distanceBar.style.background = '#f43f5e';
    elements.distanceHint.textContent = 'Ô tô đang đỗ sát cảm biến';

    elements.telemetryCurrent.innerHTML = `16.2 <span class="unit">mA</span>`;
    elements.powerTag.textContent = '👁️ Giám sát Khoảng cách';
    elements.powerTag.style.color = '#38bdf8';

    elements.camStatusTag.textContent = 'STANDBY (SLEEP)';
    elements.camStatusTag.style.background = '#334155';
    elements.aiBoundingBox.classList.remove('active');

    elements.aiProbVal.textContent = '0.94';
    elements.aiProbVal.style.color = '#f43f5e';
    elements.aiClassBadge.className = 'classification-badge badge-car';
    elements.aiClassBadge.textContent = 'XÁC NHẬN: Ô TÔ (>= 0.75)';
    elements.aiGaugeFill.style.width = '94%';
    elements.aiLatencyVal.textContent = '44 ms';

    appendLog('CNN xác nhận: Ô TÔ ĐỖ (Xác suất 94% >= 75%). Dashboard chuyển ô sang ĐỎ!', 'CAR OCCUPIED', 'log-badge-red', 'log-red');
  }, 700);
}

// PHA 4: XE RỜI ĐI (Cảm biến báo khoảng cách xa > 18cm -> Chuyển về XANH mà KHÔNG BẬT CAMERA/AI)
function runPhase4CarDeparture() {
  state.spot1.status = 'VACANT';
  state.spot1.distance = 46.8;
  state.spot1.confidence = 0.02;
  state.spot1.current_mA = 14.5;

  elements.spot1El.className = 'parking-slot vacant';
  elements.spot1StateText.textContent = 'TRỐNG (VACANT)';
  elements.objectVisual1.innerHTML = `<div class="empty-placeholder">Ô TRỐNG</div>`;
  elements.spotDist1.textContent = '46.8 cm';
  elements.spotProb1.textContent = '0.00';

  elements.telemetryDistance.innerHTML = `46.8 <span class="unit">cm</span>`;
  elements.distanceBar.style.width = '82%';
  elements.distanceBar.style.background = '#38bdf8';
  elements.distanceHint.textContent = 'Vùng an toàn (> 18cm - Xe đã rời)';

  elements.telemetryCurrent.innerHTML = `14.5 <span class="unit">mA</span>`;
  elements.powerTag.textContent = '💤 Chế độ Chờ (Standby)';
  elements.powerTag.style.color = '#10b981';

  elements.camStatusTag.textContent = 'STANDBY (SLEEP)';
  elements.camStatusTag.style.background = '#334155';
  elements.aiBoundingBox.classList.remove('active');

  elements.aiProbVal.textContent = '0.00';
  elements.aiProbVal.style.color = '#38bdf8';
  elements.aiClassBadge.className = 'classification-badge badge-human';
  elements.aiClassBadge.textContent = 'TRỐNG (XE RỜI ĐI)';
  elements.aiGaugeFill.style.width = '0%';
  elements.aiLatencyVal.textContent = '0 ms (Không chạy AI)';

  renderCanvasFrame('empty');

  appendLog('Xe rời bãi: Cảm biến khoảng cách phát hiện 46.8 cm. Chuyển ngay về TRỐNG (Màu Xanh) mà KHÔNG BẬT CAMERA/AI!', 'ZERO-AI WAKE', 'log-badge-green', 'log-green');
  appendLog('💡 Ước tính: Tiết kiệm ~165mA dòng điện và ~45ms tính toán nhờ cơ chế Sensor Fusion bất đối xứng.', 'POWER SAVING', 'log-badge-cyan', 'log-cyan');
}

// ------------------------------------------------------------------------------
// AUTO PLAY PRESENTATION CYCLE
// ------------------------------------------------------------------------------
function toggleAutoDemo() {
  if (state.isAutoPlaying) {
    clearInterval(state.autoPlayTimer);
    state.isAutoPlaying = false;
    elements.btnAutoDemo.innerHTML = `
      <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
      Tự động chạy chu trình thuyết trình
    `;
    elements.btnAutoDemo.classList.remove('btn-secondary');
    elements.btnAutoDemo.classList.add('btn-primary');
  } else {
    state.isAutoPlaying = true;
    elements.btnAutoDemo.innerHTML = `
      <svg width="18" height="18" fill="currentColor" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
      Tạm dừng chu trình
    `;
    elements.btnAutoDemo.classList.remove('btn-primary');
    elements.btnAutoDemo.classList.add('btn-secondary');

    let current = state.currentPhase;
    state.autoPlayTimer = setInterval(() => {
      current = (current % 4) + 1;
      setPhase(current);
    }, 4500);
  }
}

// ------------------------------------------------------------------------------
// LIVE MQTT WEBSOCKET CONNECTION
// ------------------------------------------------------------------------------
function connectLiveMQTT() {
  const host = elements.cfgMqttHost.value.trim();
  const topic = elements.cfgMqttTopic.value.trim();

  if (!host) {
    alert('Vui lòng nhập WebSocket URL của Broker MQTT!');
    return;
  }

  appendLog(`Đang kết nối WebSocket MQTT: ${host}...`, 'MQTT CONNECT', 'log-badge-cyan', 'log-cyan');

  if (state.mqttClient) {
    state.mqttClient.end();
  }

  try {
    const clientId = 'web_dashboard_' + Math.random().toString(16).substr(2, 8);
    state.mqttClient = mqtt.connect(host, {
      clientId: clientId,
      clean: true,
      connectTimeout: 5000,
      reconnectPeriod: 3000
    });

    state.mqttClient.on('connect', () => {
      state.mqttConnected = true;
      elements.mqttDot.className = 'status-dot connected';
      elements.mqttStatusText.textContent = 'Live MQTT: Đã kết nối';
      appendLog(`Kết nối thành công! Đang đăng ký topic: ${topic}`, 'MQTT OK', 'log-badge-green', 'log-green');
      state.mqttClient.subscribe(topic);
    });

    state.mqttClient.on('message', (receivedTopic, message) => {
      try {
        const payload = JSON.parse(message.toString());
        handleLiveTelemetry(payload);
      } catch (e) {
        appendLog(`Nhận bản tin thô: ${message.toString()}`, 'RAW MQTT', 'log-badge-amber', 'log-amber');
      }
    });

    state.mqttClient.on('error', (err) => {
      state.mqttConnected = false;
      elements.mqttDot.className = 'status-dot disconnected';
      elements.mqttStatusText.textContent = 'MQTT: Lỗi';
      appendLog(`Lỗi kết nối MQTT: ${err.message}`, 'MQTT ERROR', 'log-badge-red', 'log-red');
    });

    state.mqttClient.on('offline', () => {
      state.mqttConnected = false;
      elements.mqttDot.className = 'status-dot disconnected';
      elements.mqttStatusText.textContent = 'MQTT: Mất kết nối';
    });

  } catch (err) {
    appendLog(`Không thể khởi tạo MQTT: ${err.message}`, 'MQTT FAILED', 'log-badge-red', 'log-red');
  }
}

function handleLiveTelemetry(data) {
  // data: { spot_id, state: "OCCUPIED" | "VACANT", confidence, distance_cm, reason }
  const isOccupied = data.state === 'OCCUPIED';
  const confidence = data.confidence !== undefined ? data.confidence : 0.0;
  const distance = data.distance_cm !== undefined ? data.distance_cm : 0.0;

  elements.spot1El.className = `parking-slot ${isOccupied ? 'occupied' : 'vacant'}`;
  elements.spot1StateText.textContent = isOccupied ? 'CÓ XE (OCCUPIED)' : 'TRỐNG (VACANT)';
  elements.spotDist1.textContent = `${distance.toFixed(1)} cm`;
  elements.spotProb1.textContent = `${confidence.toFixed(2)}`;

  elements.telemetryDistance.innerHTML = `${distance.toFixed(1)} <span class="unit">cm</span>`;
  elements.telemetryCurrent.innerHTML = isOccupied ? '16.5 <span class="unit">mA</span>' : '14.5 <span class="unit">mA</span>';

  elements.aiProbVal.textContent = confidence.toFixed(2);
  elements.aiGaugeFill.style.width = `${Math.min(100, confidence * 100)}%`;

  if (isOccupied) {
    elements.objectVisual1.innerHTML = `<div class="car-graphic">CAR 01</div>`;
    elements.aiClassBadge.className = 'classification-badge badge-car';
    elements.aiClassBadge.textContent = 'XÁC NHẬN: Ô TÔ';
    renderCanvasFrame('car');
  } else {
    elements.objectVisual1.innerHTML = `<div class="empty-placeholder">Ô TRỐNG</div>`;
    elements.aiClassBadge.className = 'classification-badge badge-human';
    elements.aiClassBadge.textContent = 'KHÔNG CÓ XE (0)';
    renderCanvasFrame('empty');
  }

  appendLog(`[ESP32 Live] Trạng thái: ${data.state} | Cự ly: ${distance}cm | AI: ${(confidence*100).toFixed(0)}% | Lý do: ${data.reason}`,
            'LIVE TELEMETRY', isOccupied ? 'log-badge-red' : 'log-badge-green', isOccupied ? 'log-red' : 'log-green');
}

// ------------------------------------------------------------------------------
// EVENT LISTENERS INITIALIZATION
// ------------------------------------------------------------------------------
elements.btnPhase1.addEventListener('click', () => setPhase(1));
elements.btnPhase2.addEventListener('click', () => setPhase(2));
elements.btnPhase3.addEventListener('click', () => setPhase(3));
elements.btnPhase4.addEventListener('click', () => setPhase(4));

elements.btnAutoDemo.addEventListener('click', toggleAutoDemo);
elements.btnResetDemo.addEventListener('click', () => {
  if (state.isAutoPlaying) toggleAutoDemo();
  setPhase(1);
});

elements.btnClearLogs.addEventListener('click', () => {
  elements.logContainer.innerHTML = '';
});

// Mode Toggle
elements.btnModeSim.addEventListener('click', () => {
  elements.btnModeSim.classList.add('active');
  elements.btnModeLive.classList.remove('active');
  state.mode = 'sim';
  elements.mqttStatusText.textContent = 'Mô phỏng Sa bàn';
  elements.mqttDot.className = 'status-dot disconnected';
});

elements.btnModeLive.addEventListener('click', () => {
  elements.btnModeLive.classList.add('active');
  elements.btnModeSim.classList.remove('active');
  state.mode = 'live';
  connectLiveMQTT();
});

// Collapsible MQTT Config
elements.toggleMqttConfig.addEventListener('click', () => {
  const isHidden = elements.mqttConfigBody.style.display === 'none';
  elements.mqttConfigBody.style.display = isHidden ? 'flex' : 'none';
});

elements.btnConnectMqtt.addEventListener('click', connectLiveMQTT);

// Initialize Default State
runPhase1Baseline();
renderCanvasFrame('empty');
