# TinyML Smart Parking — CNN và ESP32-CAM

Project học tập về giám sát trạng thái **từng ô đỗ xe**, gồm pipeline huấn luyện CNN bằng Python, firmware ESP32-CAM kết hợp cảm biến khoảng cách và dashboard HTML/CSS/JavaScript.

## Bài toán và phạm vi

| Nhãn | Ý nghĩa | Thư mục lớp |
|---|---|---|
| **1** | Có xe | `occupied` |
| **0** | Không có xe | `vacant` |

Mỗi ảnh đầu vào thể hiện **một ô đỗ**. CNN nhận ảnh xám `64×64×1` và xuất điểm sigmoid cho lớp có xe. Firmware hiện dùng ngưỡng `0.75`; ngưỡng này cần được lựa chọn bằng dữ liệu validation.

CNN hiện tại được huấn luyện từ đầu; project **chưa tích hợp pretrained model hoặc transfer learning**. Có thể dùng dataset công khai mà chưa cần thu ảnh sa bàn. Nhãn 0 không phải nhãn nhận diện người/tay; khả năng xử lý vật cản cần được kiểm chứng riêng.

## Cấu trúc mã nguồn hiện có

```text
Project-3/
├── README.md
├── ai_model/
│   ├── model.py                       # Kiến trúc CNN grayscale, sigmoid
│   ├── train_and_quantize.py          # Train, validation, INT8, xuất header
│   ├── dataset_generator.py          # Sinh ảnh mô phỏng có xe / ô trống
│   ├── fetch_public_dataset.py       # Tiền xử lý ảnh đã tải và phân lớp
│   ├── dataset_collector_esp32.py     # Thu ảnh qua HTTP /capture
│   ├── tflite_to_c_array.py           # Chuyển .tflite thành mảng C
│   └── requirements.txt              # TensorFlow, NumPy, Pillow
├── firmware_esp32cam/
│   ├── esp32_smart_parking.ino        # Camera, HC-SR04, TFLite Micro, MQTT
│   ├── esp32_config.h                # GPIO, WiFi, MQTT, các ngưỡng
│   └── model_data.h                  # Dữ liệu mẫu, cần thay bằng model thật
├── dashboard/
│   ├── index.html                    # Demo và Live MQTT
│   ├── styles.css
│   └── app.js                        # Mô phỏng 4 pha, hiển thị telemetry
└── docs/
    ├── activity_flow_diagram.md
    ├── hardware_wiring.md
    ├── power_and_fusion_logic.md
    └── diorama_demo_script.md
```

`raw_data/`, `dataset/`, `output/` và `ai_model/model_data.h` được người dùng chuẩn bị hoặc được sinh khi chạy script; không phải dữ liệu/model đã có sẵn trong mã nguồn.

## Kiến trúc CNN

```text
Grayscale 64×64×1
→ Rescaling /255
→ Conv2D 16 + BatchNorm + ReLU6 + MaxPool
→ Depthwise + Pointwise 32 + MaxPool
→ Depthwise + Pointwise 48 + MaxPool
→ Depthwise + Pointwise 64
→ GlobalAveragePooling
→ Dropout 0.25
→ Dense 1 + Sigmoid
```

Mỗi phép Depthwise và Pointwise cũng được theo sau bởi BatchNorm và ReLU6. Rescaling nằm trong model, nên đầu vào trước model dùng miền pixel `0–255`.

## Cài môi trường Python

Ví dụ dùng PowerShell và Python 3.12, chạy từ thư mục gốc project:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r ai_model\requirements.txt
```

Các lệnh dưới gọi trực tiếp Python trong `.venv`, không cần kích hoạt môi trường. Nếu terminal Windows gặp lỗi in tiếng Việt, thêm `-X utf8` sau `python.exe`.

**Tương thích Keras:** script hiện gọi `model.save(saved_model_dir)` theo API lưu SavedModel cũ. Nếu dùng Keras 3, cần thay dòng đó bằng:

```python
model.save("output/parking_cnn.keras")
model.export(saved_model_dir)
```

Bước chuyển đổi hiện đọc SavedModel bằng `TFLiteConverter.from_saved_model(saved_model_dir)`. File `.keras` chỉ được tạo khi bổ sung dòng lưu trên.

## Chuẩn bị dữ liệu

### Dùng dataset công khai

Có thể dùng ảnh từng ô đỗ từ [CNRPark](https://cnrpark.it/) hoặc [PKLot](https://web.inf.ufpr.br/luizoliveira/research-interests/pklot/). Với CNRPark, ánh xạ `busy → occupied`, `free → vacant`. Nếu dùng ảnh toàn cảnh, cần cắt từng ô đỗ theo annotation trước.

Tự tải, kiểm tra nhãn và sắp xếp ảnh:

```text
ai_model/raw_data/
├── occupied/    # Nhãn 1: ảnh ô đỗ có xe
└── vacant/      # Nhãn 0: ảnh ô đỗ không có xe
```

Chạy tiền xử lý:

```powershell
cd ai_model
..\.venv\Scripts\python.exe fetch_public_dataset.py --process
```

Script chuyển grayscale, center crop hình vuông, resize `64×64` bằng Lanczos và lưu vào `dataset/occupied/`, `dataset/vacant/`. Mặc định xử lý tối đa **800 ảnh mỗi lớp**. Chạy lại có thể ghi đè các file `sample_XXXX.jpg` cùng tên.

CLI này **không tự tải dataset hoặc đọc annotation để phân lớp**; nó xử lý ảnh đã được chuẩn bị trong `raw_data/`.

Nếu ảnh đã được chuẩn bị, có thể đặt trực tiếp vào:

```text
ai_model/dataset/
├── occupied/
│   └── *.jpg, *.png, ...
└── vacant/
    └── *.jpg, *.png, ...
```

Loader train chỉ đọc file trực tiếp trong hai thư mục lớp, không duyệt thư mục con. Loader chuyển grayscale và resize thẳng `64×64`; ảnh chưa vuông nên được tiền xử lý trước. Tên lớp cũ `cars/humans` không còn được sử dụng.

### Thu ảnh từ ESP32-CAM — tùy chọn

Camera phải chạy firmware cung cấp `http://<ip>/capture`. Firmware parking trong project hiện **chưa có endpoint HTTP này**.

Từ thư mục `ai_model`, thay IP bằng IP camera:

```powershell
..\.venv\Scripts\python.exe dataset_collector_esp32.py --ip 192.168.1.50 --label occupied --count 100 --interval 1
..\.venv\Scripts\python.exe dataset_collector_esp32.py --ip 192.168.1.50 --label vacant --count 100 --interval 1
```

Ảnh được lưu vào `dataset/<label>/`. Giữ thông tin phiên chụp để phục vụ chia tập và đánh giá.

## Train và xuất model INT8

Chạy từ `ai_model`, sau khi chuẩn bị dữ liệu và xử lý tương thích Keras ở trên:

```powershell
..\.venv\Scripts\python.exe train_and_quantize.py
```

| Thiết lập mặc định | Giá trị |
|---|---|
| Epoch tối đa | 15 |
| Batch size | 32 |
| Optimizer | Adam, learning rate `0.001` |
| Loss | Binary cross-entropy |
| Chia dữ liệu | Shuffle rồi chia 80% train / 20% validation |
| Đánh giá | Accuracy và AUC trên validation |
| Callback | EarlyStopping và ReduceLROnPlateau |
| Lượng tử hóa | PTQ INT8, tối đa 150 mẫu train làm calibration |

Script chưa có tùy chọn CLI `--epochs`, `--batch-size`. Để đổi cấu hình, gọi hàm:

```powershell
..\.venv\Scripts\python.exe -c "from train_and_quantize import train_and_quantize; train_and_quantize(epochs=40, batch_size=32)"
```

Nếu thiếu thư mục lớp hoặc một lớp không có file, script tự sinh **1.600 ảnh tổng hợp**. Đây là chế độ kiểm tra pipeline; kết quả không đại diện cho chất lượng trên ảnh bãi đỗ thật.

Khi pipeline hoàn tất, các đầu ra là:

```text
ai_model/
├── output/
│   ├── parking_cnn_saved_model/
│   └── parking_cnn_int8.tflite
└── model_data.h

firmware_esp32cam/
└── model_data.h    # Bị ghi đè bằng model vừa xuất
```

Kích thước thực tế và scale/zero-point được in khi chạy. Script chưa đánh giá model INT8 trên tập test.

**Đánh giá cho báo cáo:** hiện chưa có test độc lập hoặc chia tập theo camera/ngày chụp. Cần bổ sung chia tập theo nhóm để tránh ảnh gần trùng xuất hiện ở cả train và validation; giữ test riêng và đánh giá cả float lẫn INT8. Giữ metadata camera/ngày chụp trước khi script tiền xử lý đổi tên ảnh. Dashboard mô phỏng không phải kết quả kiểm thử CNN.

## Dashboard

Mở `dashboard/index.html` bằng trình duyệt. Đây là website tĩnh, không có bước npm/build hoặc backend riêng. MQTT.js và font được tải qua mạng.

- **Sa bàn Demo:** mô phỏng ô trống, vật cản không phải xe, xe vào và xe rời đi. Điểm số, độ trễ và dòng điện là dữ liệu minh họa.
- **Live MQTT:** nhận telemetry qua WebSocket. Giao diện mặc định đặt URL `wss://broker.emqx.io:8084/mqtt` và topic `parking/+/telemetry`; có thể thay trong phần cấu hình.

Firmware và dashboard phải dùng cùng broker, topic phù hợp. ESP32 dùng MQTT TCP, còn trình duyệt dùng MQTT WebSocket. Canvas trên dashboard không phải luồng camera trực tiếp từ ESP32.

## Firmware ESP32-CAM

Sketch hướng tới AI Thinker ESP32-CAM, camera OV2640 và **HC-SR04**. Driver VL53L0X chưa được triển khai trong sketch hiện tại.

Luồng xử lý:

1. Đọc khoảng cách theo chu kỳ cấu hình `250 ms`.
2. Khoảng cách dưới `15 cm`: chụp ảnh và chạy CNN.
3. Điểm có xe `>= 0.75`: gửi `OCCUPIED`, reason `CAR_DETECTED`.
4. Điểm có xe `< 0.75`: giữ `VACANT`, reason `NO_CAR_DETECTED`.
5. Khi đang có xe và khoảng cách vượt `18 cm`: gửi `VACANT`, reason `CAR_DEPARTED_SENSOR_ONLY`, không chạy lại CNN.

Chuẩn bị Arduino IDE, ESP32 board package, PubSubClient và bản TensorFlow Lite Micro tương thích với các header/API trong sketch. Thư viện wrapper TinyML không mặc nhiên thay thế được API TFLite Micro đang dùng.

Điền WiFi, broker, topic và các ngưỡng trong `firmware_esp32cam/esp32_config.h`. Sketch cần nằm trong thư mục Arduino có tên khớp file `.ino`, ví dụ `esp32_smart_parking/`, cùng hai header firmware. Nối GPIO 0 với GND để vào chế độ flash khi nạp; tháo kết nối này và reset để chạy. Xem [đấu nối phần cứng](docs/hardware_wiring.md).

### Các điểm cần xử lý trước khi kiểm thử phần cứng

- `model_data.h` hiện chỉ chứa dữ liệu mẫu, cần thay bằng model xuất thật và kiểm tra hợp lệ.
- **Chuẩn hóa chưa đồng nhất:** model nhận pixel `0–255` rồi tự chia 255; firmware đang chia 255 trước khi lượng tử hóa. Với model này, firmware cần dùng `q = round(pixel_gray / input_scale) + input_zero_point`, rồi clamp về INT8.
- **Crop/resize chưa đồng nhất:** firmware crop `120×120` và lấy mẫu theo tọa độ nguyên; script tiền xử lý dùng Lanczos; loader train resize trực tiếp. Cần thống nhất trước khi đối chiếu Python và ESP32.
- Tensor arena đang đặt **28 KiB**, chưa xác nhận đủ. Riêng tensor `64×64×16` có 65.536 phần tử INT8; cần kiểm tra `AllocateTensors()` và đo bộ nhớ thực tế.
- Sketch đã giới hạn thời điểm chạy CNN nhưng chưa triển khai đầy đủ tắt/ngủ camera và light sleep như tài liệu thiết kế mô tả.

Các mức khoảng 18–25 KB model, 42 ms suy luận và 88% tiết kiệm năng lượng trong tài liệu là mục tiêu hoặc ước tính tham khảo, chưa phải benchmark đã được xác nhận của phiên bản này.

## Tài liệu liên quan

- [Sơ đồ hoạt động và pipeline](docs/activity_flow_diagram.md)
- [Đấu nối phần cứng](docs/hardware_wiring.md)
- [Sensor fusion và phân tích năng lượng](docs/power_and_fusion_logic.md)
- [Kịch bản demo sa bàn](docs/diorama_demo_script.md)

Tài liệu trong `docs` mô tả cả thiết kế dự kiến và ví dụ demo. Khi đánh giá chức năng đã triển khai, đối chiếu với mã nguồn và các giới hạn trong README này.
