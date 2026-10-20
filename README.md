# Wide-angle Smart Parking — Camera ROI, cảm biến khoảng cách và ESP32 INT8

Project giám sát trạng thái từng ô đỗ bằng **camera cố định góc rộng**, **cảm biến khoảng cách riêng cho từng ô** và **ESP32 thường chạy CNN INT8 kết hợp hai nguồn (sensor fusion)**. Camera, gateway và node suy luận là các thiết bị/thành phần tách biệt.

```text
Camera góc rộng → Gateway crop ROI → CNN INT8 trên ESP32 ─┐
Cảm biến khoảng cách từng ô → ESP32 lọc và xác nhận ──────┴→ Fusion → Gateway → Web
```

| Nhãn/trạng thái | Ý nghĩa |
|---|---|
| `1` / `occupied` | Có xe |
| `0` / `vacant` | Không có xe |
| `unknown`, `label: null` | Chưa có kết quả hợp lệ, ví dụ mất kết nối ESP32 |

ESP32 không nhận video HD, không giải mã JPEG và không điều khiển camera. Gateway trên PC/mini PC nhận frame, cắt vùng từng ô và gửi **4096 byte pixel uint8** mỗi request. Trong thiết kế đích, ESP32 chạy TFLite Micro, đọc cảm biến tương ứng và trả kết quả fusion cùng bằng chứng hai nguồn. Các ô được xử lý tuần tự trên một node.

## Kiến trúc hệ thống

```mermaid
flowchart LR
    Camera[Camera góc rộng cố định] -->|Frame mới| Gateway[FastAPI Gateway]
    Config[Cấu hình ROI và ánh xạ slot_id] --> Gateway
    Gateway --> ROI[Crop ROI và grayscale 64x64]
    ROI -->|4096 byte mỗi ô và metadata| CNN[CNN INT8 trên ESP32 thường]
    Sensors[Cảm biến khoảng cách riêng cho từng ô] --> Filter[Lọc mẫu và hysteresis trên ESP32]
    CNN --> Fusion[Fusion trên ESP32: kiểm tra độ mới và đồng thuận]
    Filter --> Fusion
    Fusion -->|Nhãn cuối 1/0/unknown và bằng chứng hai nguồn| Gateway
    Gateway --> Web[Dashboard từng ô]
    Train[Train và đánh giá trên PC/GPU] --> Export[Model INT8 và header C]
    Export --> CNN
    Export -. test ảnh độc lập .-> Reference[Backend tham chiếu CNN]
```

Luồng triển khai dùng `target=esp32`. Backend có chế độ `target=backend` để so sánh float/INT8 trên máy tính; chế độ này phải được chọn rõ ràng, không tự thay thế ESP32 nếu thiết bị lỗi.

## SSD — System Sequence Diagram

SSD dưới đây mô tả luồng đích với người vận hành, camera ngoài, ESP32 và cảm biến khoảng cách của từng ô. SSD là sơ đồ tuần tự hệ thống, không phải thuật toán Single Shot Detector.

```mermaid
sequenceDiagram
    actor Operator as Người vận hành
    participant Gateway as Web và FastAPI Gateway
    participant Camera as Camera góc rộng
    participant ESP32 as ESP32 CNN và fusion
    participant Sensor as Cảm biến khoảng cách theo ô
    Operator->>Gateway: Kiểm tra bãi xe với ROI và ánh xạ cảm biến
    Gateway->>Camera: Lấy frame mới
    Camera-->>Gateway: Frame toàn cảnh
    loop Từng ô theo slot_id
        Note over Gateway: Crop ROI, grayscale và resize 64x64
        Gateway->>ESP32: Tensor 4096 byte, slot_id, request_id, model hash, threshold
        ESP32->>Sensor: Đọc cảm biến đúng ô, lọc và xác nhận trạng thái
        Sensor-->>ESP32: Khoảng cách hoặc lỗi đo
        Note over ESP32: Chạy CNN INT8; kiểm tra độ mới hai nguồn
        alt Hai nguồn hợp lệ và cùng xác nhận có xe
            ESP32-->>Gateway: occupied, label 1 và bằng chứng hai nguồn
        else Hai nguồn hợp lệ và cùng xác nhận trống
            ESP32-->>Gateway: vacant, label 0 và bằng chứng hai nguồn
        else Mâu thuẫn, thiếu dữ liệu hoặc quá hạn
            ESP32-->>Gateway: unknown, label null và lý do
        else ESP32 mất kết nối hoặc phản hồi không hợp lệ
            Note over Gateway: Đánh dấu UNKNOWN; không suy ra ô trống
        end
    end
    Gateway-->>Operator: Trạng thái cuối từng ô và thông tin CNN/khoảng cách
    Note over Operator,Gateway: Upload ảnh cũ chỉ test CNN; không ghép với khoảng cách hiện tại
```

Nguồn Mermaid: [kiến trúc](docs/diagrams/system_architecture.mmd), [SSD](docs/diagrams/system_sequence.mmd). Chi tiết giao thức và giới hạn: [system_architecture.md](docs/system_architecture.md).

## Kết hợp khoảng cách và car detection

Mỗi `slot_id` ghép đúng **một ROI và một cảm biến**. ESP32 lọc khoảng cách, dùng hai ngưỡng vào/ra để chống dao động và kết hợp với CNN:

| Khoảng cách hợp lệ, còn mới | CNN hợp lệ | Trạng thái cuối |
|---|---|---|
| Có vật thể | Có xe | `1 / occupied` |
| Trống | Không có xe | `0 / vacant` |
| Hai nguồn mâu thuẫn, thiếu hoặc quá hạn | Bất kỳ | `unknown`, `label: null` |

Không có echo không được coi là ô trống. Ngưỡng khoảng cách phải hiệu chỉnh theo vị trí lắp trên sa bàn; ngưỡng CNN chọn theo validation. Upload ảnh cũ chỉ test CNN, không ghép với khoảng cách đang đo.

**Phân biệt thiết kế và code hiện tại:** các sơ đồ mô tả hệ thống đích có fusion. Gateway, API và firmware hiện mới có nhánh ảnh/CNN; chưa có driver khoảng cách hay logic fusion. Kết quả `label` của API hiện tại vẫn là nhãn CNN. Xem [đặc tả sensor fusion và các ca kiểm thử](docs/sensor_fusion.md).

## Cấu trúc project

```text
Project-3/
├── ai_model/                              # Huấn luyện và đánh giá offline
│   ├── __init__.py
│   ├── model.py
│   ├── dataset_io.py                      # Preprocessing dùng chung với gateway
│   ├── prepare_dataset.py
│   ├── check_dataset.py
│   ├── train_and_quantize.py
│   ├── evaluate_model.py
│   ├── tflite_to_c_array.py
│   ├── requirements.txt
│   └── requirements-gpu.txt
├── backend/                               # Gateway camera và service FastAPI
│   ├── __init__.py
│   ├── app.py                             # API, Swagger, dashboard
│   ├── inference.py                       # Preprocessing và mode tham chiếu
│   ├── roi.py                             # ROI cố định theo độ phân giải camera
│   ├── esp32_client.py                    # Gửi 4096 byte và kiểm tra response
│   ├── requirements.txt                  # Gateway ESP32, không yêu cầu TensorFlow
│   ├── requirements-reference.txt        # Thêm TensorFlow cho mode tham chiếu
│   └── requirements-test.txt
├── config/
│   └── parking.example.json               # Mẫu tọa độ, chưa hiệu chỉnh camera thật
├── firmware_esp32/
│   └── esp32_parking_inference/            # Tên thư mục khớp Arduino sketch
│       ├── esp32_parking_inference.ino
│       ├── esp32_config.h
│       └── model_data.h                   # INT8 weights và SHA-256
├── dashboard/
│   ├── index.html
│   ├── image-test.js                      # Upload ảnh đơn/toàn cảnh, kết quả ROI
│   └── styles.css
├── docs/
│   ├── system_architecture.md
│   ├── activity_flow_diagram.md
│   ├── sensor_fusion.md                     # Đặc tả kết hợp khoảng cách và CNN
│   ├── hardware_wiring.md
│   ├── model_service.md
│   ├── training_and_evaluation.md
│   ├── gpu_training.md
│   └── diagrams/
│       ├── system_architecture.mmd
│       └── system_sequence.mmd
├── tests/
│   └── test_gateway.py                    # Gateway, ROI và thiết bị HTTP giả
└── README.md
```

Dataset và model output nằm trong `ai_model/dataset/`, `ai_model/output/`, được bỏ qua bởi Git. Giữ nguyên dataset CNR-EXT và các model đã train khi thay đổi kiến trúc. File `config/parking.json` là cấu hình camera thật, cũng được bỏ qua bởi Git.

## Chạy gateway và web

Từ thư mục gốc `D:\Project-3`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-reference.txt
```

**Test trên máy tính khi chưa có ESP32**:

```powershell
.\.venv\Scripts\python.exe -m backend.app
```

Mở http://127.0.0.1:8000/ và chọn **Backend · tham chiếu**. Model mặc định là `ai_model/output/run_gpu01`. Không cần môi trường GPU để thử ảnh trên Windows.

**Triển khai với ESP32**: copy `config/parking.example.json` thành `config/parking.json`, hiệu chỉnh ROI theo camera thật, rồi chạy:

```powershell
.\.venv\Scripts\python.exe -m backend.app --esp32-url http://192.168.1.50 --roi-config config\parking.json
```

Thay IP bằng địa chỉ ESP32 in trên Serial Monitor. Trên web, chọn **ESP32 · INT8**, chọn ảnh đã crop một ô hoặc ảnh toàn cảnh theo ROI, rồi kiểm tra. Giao diện hiển thị rõ thiết bị thực hiện suy luận. `/docs` là Swagger UI.

Khi đã cấu hình ESP32, gateway mặc định không nạp TensorFlow để suy luận trên PC. Chỉ thêm `--enable-reference` khi muốn bật đồng thời chế độ đối chiếu trên backend.

Máy chỉ chạy gateway cho ESP32 có thể cài `backend/requirements.txt` để không kéo TensorFlow; file `requirements-reference.txt` ở ví dụ cài đặt trên bao gồm cả chế độ test máy tính.

### Các API chính

| API | Công dụng |
|---|---|
| `GET /health` | Gateway đã khởi động, không xác nhận ESP32 đang online |
| `GET /api/status` | Model, ngưỡng, target khả dụng, số ROI |
| `GET /api/rois` | Cấu hình ROI, không trả URL camera |
| `POST /api/predict` | Test ảnh một ô đỗ |
| `POST /api/predict-frame` | Upload ảnh toàn cảnh, xử lý từng ROI |
| `POST /api/predict-camera` | Lấy HTTP snapshot từ camera đã cấu hình và xử lý ROI |

Hai API upload dùng multipart field `file`. Query `target=esp32` (mặc định) hoặc `target=backend`; ESP32 chỉ hỗ trợ `model=int8`. Test bằng backend tham chiếu:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/predict?target=backend&model=int8" -F "file=@D:/images/parking_slot.jpg"
```

Chi tiết request, response và lỗi: [model_service.md](docs/model_service.md). Chưa có vòng lặp camera tự động, adapter RTSP/ONVIF hoặc giao diện vẽ ROI; hiện cấu hình ROI bằng JSON và lấy ảnh theo yêu cầu.

## ROI và preprocessing

`config/parking.example.json` khai báo `reference_width`, `reference_height`, `camera_id`, các hình chữ nhật `x,y,width,height` và `snapshot_url` tùy chọn. Tọa độ mẫu chỉ minh họa, không được tự dùng làm tọa độ thật.

Mỗi ROI được grayscale → center crop hình vuông → bilinear resize 64×64. Đây là cùng preprocessing lúc train. Chọn vùng đủ vuông và giữ trọn xe; ROI hình chữ nhật dài có thể bị center crop cắt mất xe. Nếu đổi sang padding/hiệu chỉnh phối cảnh, cần đánh giá và có thể train lại.

Độ phân giải có thể thay đổi nếu giữ tỷ lệ khung hình; góc nhìn, zoom hoặc vị trí camera thay đổi thì phải hiệu chỉnh ROI. Chưa có xử lý méo fisheye hay ROI đa giác.

## Train CNN và kiểm tra model

CNN được train từ đầu, không dùng pretrained model:

```text
64×64×1 → Rescaling /255 → Conv 16 + Pool
→ Depthwise/Pointwise 32 + Pool → Depthwise/Pointwise 48 + Pool
→ Depthwise/Pointwise 64 → GAP → Dropout 0.25 → Dense 1 + Sigmoid
```

Dataset có `train/val/test`, mỗi tập gồm `occupied/` và `vacant/`. Chia theo ngày/camera/chuỗi chụp trước khi train để tránh rò rỉ ảnh gần trùng. Model train float32, lưu checkpoint tốt nhất theo validation rồi PTQ INT8 với calibration từ train.

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\check_dataset.py --dataset-dir ai_model\dataset
.\.venv\Scripts\python.exe -X utf8 ai_model\train_and_quantize.py --dataset-dir ai_model\dataset --output-dir ai_model\output\run02 --epochs 40 --batch-size 32 --device cpu
```

Train RTX 3050 Ti qua Ubuntu/WSL2: [gpu_training.md](docs/gpu_training.md). Toàn bộ quy trình chia dữ liệu, chọn ngưỡng validation và đánh giá float/INT8 trên test: [training_and_evaluation.md](docs/training_and_evaluation.md).

Ngưỡng gateway lấy từ `--threshold`, nếu không có thì dùng báo cáo validation, cuối cùng mới dùng `0.75` mặc định. Header firmware nhận ngưỡng từ request để so sánh nhất quán. Điểm sigmoid không phải tỷ lệ dự đoán đúng.

## Nạp model và firmware ESP32

Xuất lại header khi đổi model:

```powershell
.\.venv\Scripts\python.exe -X utf8 ai_model\tflite_to_c_array.py ai_model\output\run_gpu01\parking_cnn_int8.tflite firmware_esp32\esp32_parking_inference\model_data.h
```

`--export-firmware` của script train cũng xuất vào đường dẫn mới. Header chứa SHA-256 để gateway kiểm tra đúng model đang chạy trên node.

Mở `firmware_esp32/esp32_parking_inference/esp32_parking_inference.ino` bằng Arduino IDE, dùng board ESP32 DevKit/WROOM và thư viện TFLite Micro tương thích API trong sketch. Cấu hình Wi-Fi tại `esp32_config.h`. Firmware hiện cung cấp `GET /health` và `POST /infer` cho CNN; driver cảm biến khoảng cách và fusion còn cần triển khai theo [đặc tả](docs/sensor_fusion.md).

Header hiện được tạo từ `run_gpu01` (20.048 byte). Arena ban đầu đặt **160 KiB**, cần đo lại trên board; kích thước trọng số không phải nhu cầu RAM toàn bộ. Nếu `AllocateTensors()` thất bại, không được coi thiết bị đã sẵn sàng. Backend không tự chuyển sang chạy model thay ESP32 khi lỗi.

## Kiểm chứng và giới hạn

Chạy kiểm tra gateway với model local và ESP32 HTTP giả:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-test.txt
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

Các bài test xác minh crop/giao thức/UNKNOWN và mode tham chiếu; không thay thế compile hoặc đo trên ESP32 thật.

- Thiết kế đích dùng cả khoảng cách và CNN; code hiện chưa có nhánh cảm biến/fusion.
- Có gateway/API, preprocessing ROI, transport ESP32 và firmware nguồn; chế độ backend tham chiếu hỗ trợ kiểm tra trên máy tính.
- Chưa xác nhận compile/chạy firmware trên ESP32 thật vì môi trường chưa có Arduino toolchain/TFLite Micro cho board.
- Chưa kiểm chứng camera thật, FPS nhiều ô, RAM/latency ESP32 hoặc điện năng. Không có cam kết tiết kiệm pin từ thiết kế trước.
- Test bằng dữ liệu công khai không bảo đảm độ chính xác trên camera góc rộng thực tế. Cần ảnh cùng góc nhìn và phân tích lỗi/nhãn/ROI.
- Request lỗi, timeout, sai hash hoặc sai ID phải được báo lỗi/UNKNOWN; không được đổi thành nhãn không có xe.

Tài liệu: [kiến trúc và giao thức](docs/system_architecture.md), [luồng hoạt động](docs/activity_flow_diagram.md), [kết nối thiết bị](docs/hardware_wiring.md), [FastAPI](docs/model_service.md).
