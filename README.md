# TinyML Smart Parking System (ESP32-CAM & Sensor Fusion)

Hệ thống giám sát trạng thái từng ô đỗ xe (Trống / Có xe) chạy trên vi điều khiển hạn chế tài nguyên **ESP32-CAM**, ứng dụng mạng nơ-ron tích chập siêu nhẹ **Ultra-Lightweight CNN (INT8)** và cơ chế kết hợp cảm biến bất đối xứng **Wake-on-Sensor**.

---

## 📁 Cấu Trúc Thư Mục Dự Án

```
d:/Project-3/
├── ai_model/                         # Module thiết kế, huấn luyện & lượng tử hóa AI
│   ├── model.py                      # Kiến trúc Depthwise Separable CNN (64x64x1, GAP, Sigmoid)
│   ├── dataset_generator.py          # Bộ sinh dataset sa bàn mô phỏng & Data Augmentation
│   ├── train_and_quantize.py         # Huấn luyện & Full Integer INT8 Post-Training Quantization
│   ├── tflite_to_c_array.py          # Chuyển đổi .tflite sang mảng C array cho vi điều khiển
│   ├── dataset_collector_esp32.py    # Thu thập ảnh thực tế từ stream ESP32-CAM qua WiFi
│   ├── requirements.txt              # Thư viện Python cần thiết (TensorFlow, Pillow, NumPy)
│   └── model_data.h                  # Header C chứa mảng byte tĩnh mô hình INT8 (~18KB)
│
├── firmware_esp32cam/                # Firmware nạp cho vi điều khiển ESP32-CAM
│   ├── esp32_smart_parking.ino       # Code chính (Wake-on-Sensor FSM, OV2640, TFLite Micro, MQTT)
│   ├── esp32_config.h                # Cấu hình Pins, WiFi, MQTT Topics, Ngưỡng 0.75, Hysteresis
│   └── model_data.h                  # Mảng C array mô hình INT8 tích hợp sẵn
│
├── dashboard/                        # Web Dashboard trực quan hóa & Điều khiển Sa bàn
│   ├── index.html                    # Giao diện chính (Hỗ trợ Sa bàn 4 pha & Live MQTT WebSocket)
│   ├── styles.css                    # Thiết kế Glassmorphism / Cyber Dark Mode cao cấp
│   └── app.js                        # Logic mô phỏng 4 pha, vẽ canvas 64x64 và MQTT client
│
└── docs/                             # Tài liệu kỹ thuật chi tiết
    ├── activity_flow_diagram.md      # Sơ đồ hoạt động Mermaid & giải thích chi tiết toàn bộ chu trình
    ├── hardware_wiring.md            # Sơ đồ đấu nối dây, cầu phân áp bảo vệ chân Echo
    ├── power_and_fusion_logic.md     # Phân tích tiết kiệm 88% năng lượng pin & máy trạng thái FSM
    └── diorama_demo_script.md        # Kịch bản thuyết trình demo 4 pha chuẩn bài báo cáo
```

---

## 🚀 Hướng Dẫn Bắt Đầu Nhanh

### 1. Huấn Luyện & Lượng Tử Hóa AI Model

Quy ước nhãn: **1 = có xe (`occupied`)**, **0 = không có xe (`vacant`)**.
Mỗi ảnh đầu vào là một ô đỗ, chuyển về grayscale 64×64. Đầu ra sigmoid là điểm số có xe; firmware hiện dùng ngưỡng 0.75 và cần hiệu chỉnh trên validation.

Chuẩn bị ảnh từ dataset công khai (CNRPark: `busy` → `occupied`, `free` → `vacant`; PKLot: occupied → 1, vacant → 0):

```text
ai_model/dataset/
├── occupied/  # Nhãn 1: có xe
└── vacant/    # Nhãn 0: không có xe
```

Nếu dùng script tiền xử lý, đặt ảnh vào `ai_model/raw_data/occupied/` và `ai_model/raw_data/vacant/`, rồi chạy `python fetch_public_dataset.py --process` trong `ai_model`.
Tên thư mục cũ `cars/humans` không còn được dùng. Giữ thông tin camera/ngày chụp để chia tập theo nhóm trước khi tiền xử lý; script train hiện chỉ chia ngẫu nhiên 80/20 và chưa có test độc lập.
Nếu không có đủ hai thư mục dữ liệu, script dùng ảnh tổng hợp có xe/ô trống để kiểm tra pipeline; kết quả này không đại diện cho độ chính xác trên ảnh thật.
Model chưa được huấn luyện riêng để nhận diện người/tay. Pha nhiễu trên dashboard là mô phỏng, không chứng minh khả năng loại bỏ người.

```bash
# Di chuyển vào thư mục ai_model
cd ai_model

# Cài đặt thư viện
pip install -r requirements.txt

# Chạy huấn luyện và tự động lượng tử hóa INT8 sang file C array
python train_and_quantize.py
```
*Kết quả:* Mô hình INT8 có kích thước chỉ **~18KB - 22KB**, các tham số `scale` và `zero_point` được in ra và tự động ghi đè vào file `firmware_esp32cam/model_data.h`.

### 2. Nạp Firmware Cho ESP32-CAM
1. Mở file `firmware_esp32cam/esp32_smart_parking.ino` bằng **Arduino IDE**.
2. Cài đặt board **ESP32 by Espressif Systems** (Chọn board: *AI Thinker ESP32-CAM*).
3. Cài đặt thư viện qua Library Manager:
   - `EloquentTinyML` hoặc `TensorFlowLite_ESP32`
   - `PubSubClient` (của Nick O'Leary)
4. Mở file `esp32_config.h` để điền tên WiFi, mật khẩu và Broker MQTT.
5. Nối chân **GPIO 0 xuống GND** & nhấn Reset để vào Flash Mode &rarr; Bấm **Upload**.
6. Sau khi nạp xong, rút chân GPIO 0 ra khỏi GND và nhấn nút Reset trên ESP32-CAM.

### 3. Mở Web Dashboard & Trình Diễn Sa Bàn
- Nhấp đúp mở trực tiếp file `dashboard/index.html` trên bất kỳ trình duyệt nào (Chrome, Edge, Firefox).
- Bấm vào các nút **01 Baseline**, **02 Nhiễu người**, **03 Đỗ xe**, **04 Xe rời đi** hoặc nút **Tự động chạy chu trình thuyết trình** để trải nghiệm kịch bản 4 pha.
- Nếu muốn xem dữ liệu từ ESP32-CAM thật qua WiFi: chuyển sang tab **Live MQTT** và bấm **Kết nối MQTT Broker**.
