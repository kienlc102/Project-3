(() => {
  const el = (id) => document.getElementById(id);
  const form = el('image-test-form');
  const input = el('parking-image');
  const model = el('prediction-model');
  const target = el('prediction-target');
  const scope = el('prediction-scope');
  const button = el('predict-image-button');
  const message = el('upload-message');
  let selectedFile = null, previewUrl = null, ready = false, busy = false;

  function controls() {
    button.disabled = busy || !ready || !selectedFile;
    button.textContent = busy ? 'Đang phân tích ảnh…' : 'Kiểm tra ảnh';
    input.disabled = busy;
    model.disabled = busy || !ready;
    target.disabled = busy || !ready;
    scope.disabled = busy;
    if (target.value === 'esp32') { model.value = 'int8'; model.disabled = true; }
    form.setAttribute('aria-busy', String(busy));
  }
  function clearResult() {
    el('prediction-result').className = 'prediction-result';
    el('prediction-label').textContent = 'Chưa có kết quả';
    el('prediction-description').textContent = 'Chọn ảnh và bấm “Kiểm tra ảnh” để bắt đầu.';
    el('prediction-details').hidden = true;
    el('input-preview-row').hidden = true;
    el('model-input-preview').removeAttribute('src');
    el('prediction-score-fill').style.width = '0%';
    el('roi-results').hidden = true;
    el('roi-results-body').replaceChildren();
  }
  function selectFile(file) {
    if (busy || !file) return;
    selectedFile = null;
    clearResult();
    message.textContent = '';
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    el('upload-preview').hidden = true;
    el('upload-preview').removeAttribute('src');
    el('upload-placeholder').hidden = false;
    el('upload-filename').textContent = 'Chưa chọn ảnh';
    if (!file.size || file.size > 10 * 1024 * 1024) {
      message.textContent = 'Hãy chọn ảnh không rỗng, tối đa 10 MB.';
    } else if (!/\.(jpe?g|png|webp|bmp)$/i.test(file.name)) {
      message.textContent = 'Chỉ hỗ trợ JPG, PNG, WebP hoặc BMP.';
    } else {
      selectedFile = file;
      previewUrl = URL.createObjectURL(file);
      el('upload-preview').src = previewUrl;
      el('upload-preview').hidden = false;
      el('upload-placeholder').hidden = true;
      el('upload-filename').textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} KB`;
    }
    controls();
  }
  async function request(url, options = {}, timeout = 15000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { ...options, signal: controller.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Yêu cầu không hợp lệ. Hãy kiểm tra file ảnh.');
      return data;
    } finally { clearTimeout(timer); }
  }
  async function connect() {
    ready = false;
    el('backend-status').textContent = 'Đang kết nối…';
    el('backend-status').className = 'backend-status';
    el('retry-backend').hidden = true;
    controls();
    try {
      if (!/^https?:$/.test(location.protocol)) throw new Error('Hãy bật service và mở http://127.0.0.1:8000.');
      const data = await request('/api/status');
      if (!data.ready || !data.models?.length) throw new Error('Model chưa sẵn sàng.');
      const previous = model.value;
      model.replaceChildren(...data.models.map((type) => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type === 'int8' ? 'INT8' : 'Float32';
        return option;
      }));
      if (data.models.includes(previous)) model.value = previous;
      target.replaceChildren(...data.execution_targets.map((type) => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type === 'esp32' ? 'ESP32 · INT8' : 'Backend · tham chiếu';
        return option;
      }));
      target.value = data.execution_targets.includes('esp32') ? 'esp32' : 'backend';
      const source = data.threshold_source === 'validation' ? 'chọn trên validation' : data.threshold_source === 'default' ? 'mặc định, chưa chọn trên validation' : 'đã cấu hình';
      el('prediction-config').textContent = `${data.run} · Ngưỡng ${data.threshold.toFixed(2)} (${source}) · ${data.roi_count} ROI. ${data.execution_targets.includes('esp32') ? 'Đã cấu hình địa chỉ ESP32; kết nối được kiểm tra khi gửi ảnh.' : 'Chưa cấu hình ESP32, chỉ có chế độ backend tham chiếu.'}`;
      el('backend-status').textContent = 'Gateway sẵn sàng';
      el('backend-status').className = 'backend-status is-ready';
      message.textContent = '';
      ready = true;
    } catch (error) {
      el('backend-status').textContent = 'Chưa kết nối backend';
      el('backend-status').className = 'backend-status is-offline';
      el('prediction-config').textContent = 'Model chưa sẵn sàng.';
      message.textContent = error.message.startsWith('Hãy') ? error.message : 'Không kết nối được service. Kiểm tra server rồi bấm “Kết nối lại”.';
      el('retry-backend').hidden = false;
    }
    controls();
  }
  input.addEventListener('change', () => selectFile(input.files[0]));
  model.addEventListener('change', () => { clearResult(); message.textContent = ''; });
  target.addEventListener('change', () => { clearResult(); message.textContent = ''; controls(); });
  scope.addEventListener('change', () => { clearResult(); message.textContent = ''; });
  el('retry-backend').addEventListener('click', connect);
  el('upload-preview').addEventListener('error', () => {
    if (!selectedFile || busy) return;
    selectedFile = null;
    el('upload-preview').hidden = true;
    el('upload-placeholder').hidden = false;
    message.textContent = 'Không đọc được ảnh. Hãy chọn một ảnh khác.';
    controls();
  });
  for (const name of ['dragenter', 'dragover', 'dragleave', 'drop']) {
    el('image-dropzone').addEventListener(name, (event) => {
      event.preventDefault();
      el('image-dropzone').classList.toggle('is-dragging', !busy && (name === 'dragenter' || name === 'dragover'));
      if (name === 'drop' && !busy) {
        if (event.dataTransfer.files.length === 1) selectFile(event.dataTransfer.files[0]);
        else message.textContent = 'Mỗi lần kiểm tra một ảnh ô đỗ.';
      }
    });
  }
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!ready || !selectedFile || busy) return;
    busy = true;
    clearResult();
    el('prediction-label').textContent = 'Đang phân tích…';
    message.textContent = '';
    controls();
    try {
      const body = new FormData();
      body.append('file', selectedFile);
      const route = scope.value === 'frame' ? '/api/predict-frame' : '/api/predict';
      const data = await request(`${route}?model=${encodeURIComponent(model.value)}&target=${encodeURIComponent(target.value)}`, { method: 'POST', body }, 120000);
      if (scope.value === 'frame') {
        el('prediction-label').textContent = data.complete ? `Đã kiểm tra ${data.results.length} ô` : 'Có ô chưa xác định';
        el('prediction-description').textContent = `Có xe: ${data.counts.occupied} · Không có xe: ${data.counts.vacant} · Chưa xác định: ${data.counts.unknown}`;
        for (const result of data.results) {
          const row = document.createElement('tr');
          for (const value of [result.slot_id, '', result.status === 'ok' ? result.result : 'Chưa xác định', result.status === 'ok' ? `${(result.car_score * 100).toFixed(1)}%` : '—', result.status === 'ok' ? `${result.latency_ms.toFixed(2)} ms` : '—']) {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.append(cell);
          }
          if (result.input_preview) {
            const img = document.createElement('img');
            img.src = result.input_preview;
            img.alt = `ROI ${result.slot_id}`;
            row.children[1].append(img);
          }
          if (result.error) row.children[2].title = result.error;
          el('roi-results-body').append(row);
        }
        el('roi-results').hidden = false;
        message.textContent = data.complete ? `Đã suy luận tại ${target.value === 'esp32' ? 'ESP32' : 'backend tham chiếu'}.` : 'Có lỗi thiết bị. Các ô không có kết quả hợp lệ được giữ là chưa xác định.';
        return;
      }
      el('prediction-result').classList.add(data.label === 1 ? 'is-occupied' : 'is-vacant');
      el('prediction-label').textContent = data.result;
      el('prediction-description').textContent = `Nhãn ${data.label} · ${data.label === 1 ? 'Ô đỗ có xe' : 'Ô đỗ không có xe'}`;
      el('prediction-score').textContent = `${(data.car_score * 100).toFixed(1)}%`;
      el('prediction-threshold').textContent = data.threshold.toFixed(2);
      el('prediction-used-model').textContent = data.model === 'int8' ? 'INT8' : 'Float32';
      el('prediction-used-target').textContent = data.execution_target === 'esp32' ? 'ESP32' : 'Backend tham chiếu';
      el('prediction-time').textContent = `${data.latency_ms.toFixed(2)} ms`;
      el('prediction-score-fill').style.width = `${data.car_score * 100}%`;
      el('prediction-details').hidden = false;
      el('model-input-preview').src = data.input_preview;
      el('input-preview-row').hidden = false;
      message.textContent = 'Đã kiểm tra bằng model thực tế.';
    } catch (error) {
      clearResult();
      el('prediction-label').textContent = 'Chưa thể dự đoán';
      message.textContent = error.name === 'AbortError' ? 'Yêu cầu quá thời gian chờ. Hãy thử lại.' : error instanceof TypeError ? 'Mất kết nối service. Hãy kết nối lại.' : error.message;
      if (error instanceof TypeError) {
        ready = false;
        el('backend-status').textContent = 'Chưa kết nối backend';
        el('backend-status').className = 'backend-status is-offline';
        el('retry-backend').hidden = false;
      }
    } finally { busy = false; controls(); }
  });
  window.addEventListener('beforeunload', () => { if (previewUrl) URL.revokeObjectURL(previewUrl); });
  connect();
})();
