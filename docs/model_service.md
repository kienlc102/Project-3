# FastAPI gateway: camera ROI và ESP32

> API/web hiện tại chỉ kiểm tra CNN, kể cả khi chọn ESP32. Thiết kế mới yêu cầu kết hợp cảm biến khoảng cách; driver, fusion và response hai nguồn chưa được triển khai. Không dùng nhãn CNN hiện tại như kết quả fusion. Xem [đặc tả](sensor_fusion.md).

## Cấu trúc backend

```text
backend/
├── app.py                 # App factory, lifespan, dashboard và CLI
├── api/
│   ├── routes.py          # Tổng hợp các router
│   ├── uploads.py         # Đọc upload với giới hạn dung lượng
│   └── endpoints/
│       ├── status.py      # Health và trạng thái gateway
│       ├── prediction.py  # Dự đoán một ô đỗ
│       └── camera.py      # Cấu hình ROI, dự đoán frame và camera
├── config/
│   ├── settings.py        # Đường dẫn mặc định và giới hạn upload
│   └── camera.py          # Đọc cấu hình ROI từ JSON
├── database/              # Dành cho lưu trữ; chưa có triển khai
├── model/inference.py     # Nạp model, tiền xử lý và suy luận
├── schemas/
│   ├── camera.py          # Schema camera, kiểm tra và cắt ROI
│   └── prediction.py      # Schema response dự đoán
└── service/
    ├── esp32_client.py    # HTTP transport tới ESP32
    └── prediction.py      # Kiểm tra target và xử lý các ROI trong frame
```

Các module cũ `backend.inference`, `backend.esp32_client` và `backend.roi`
đã chuyển vào các package trên. Lệnh chạy và đường dẫn API giữ nguyên.
File cấu hình camera vẫn nằm ở `config/parking.json` tại gốc project;
`backend/config/` chứa mã Python đọc cấu hình.

## Chạy bằng Docker Compose

Cần Docker Desktop đang chạy Linux containers và model đã có trong
`ai_model/output/run_gpu01` (file `.keras` và/hoặc `parking_cnn_int8.tflite`).
Image dùng Python 3.11 và TensorFlow CPU; không cần GPU.

Từ thư mục gốc project:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f backend
```

Frontend quản lý: http://localhost:3000/ — Swagger: http://localhost:8000/docs.
Compose khởi động cả frontend Next.js và backend; xem [hướng dẫn frontend](frontend.md).
Dashboard kiểm tra cũ vẫn ở http://localhost:8000/.
Mặc định chạy backend tham chiếu; chọn **Backend · tham chiếu** trên dashboard.

Để đổi cổng, thư mục model hoặc địa chỉ ESP32, sao chép `.env.example` thành
`.env` và sửa các biến tương ứng:

```dotenv
BACKEND_PORT=8000
MODEL_DIR=./ai_model/output/run_gpu01
ESP32_URL=http://192.168.1.50
```

Sau đó chạy lại `docker compose up -d`. Khi `ESP32_URL` có giá trị, backend
chạy chế độ ESP32, không nạp model tham chiếu; cần file `parking_cnn_int8.tflite`
trong thư mục model để kiểm tra hash. ESP32 phải truy cập được từ container.

Model và thư mục `config/` được mount chỉ đọc. Muốn dùng camera ROI, tạo
`config/parking.json` từ `config/parking.example.json`, chỉnh lại theo camera
thực tế rồi chạy `docker compose restart backend`. Nếu camera chạy trên máy
Windows host, dùng `host.docker.internal` thay cho `localhost` trong snapshot URL.
Thay model cũng cần restart backend; sửa mã nguồn cần `docker compose up --build -d`.

Dừng dịch vụ: `docker compose down`.

## Khởi động

Tại `D:\Project-3`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-reference.txt
.\.venv\Scripts\python.exe -m backend.app
```

- Dashboard: http://127.0.0.1:8000/
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json

Khi chưa có ESP32, chọn **Backend · tham chiếu** trên giao diện. Chạy trên CPU Windows, không cần môi trường train GPU. Đây là mode kiểm tra; luồng triển khai thực tế yêu cầu ESP32.

Chạy với node ESP32 và camera đã hiệu chỉnh ROI:

```powershell
.\.venv\Scripts\python.exe -m backend.app --esp32-url http://192.168.1.50 --roi-config config\parking.json
```

`config/parking.json` được tạo từ `config/parking.example.json` rồi sửa theo ảnh thật. Không dùng tọa độ mẫu như kết quả đã hiệu chỉnh. IP ESP32 lấy từ Serial Monitor của firmware.

## Test trên web

1. Chọn/upload ảnh, tối đa 10 MB, JPG/PNG/WebP/BMP.
2. Chọn **Một ô đỗ** nếu đã crop; chọn **Toàn cảnh** nếu đã cấu hình ROI.
3. Chọn **ESP32 · INT8** hoặc **Backend · tham chiếu**.
4. Chỉ backend tham chiếu cho phép chọn Float32; ESP32 dùng INT8.
5. Kiểm tra kết quả và thiết bị suy luận. Ảnh toàn cảnh trả bảng từng ô; ô lỗi hiển thị **Chưa xác định**.

Model không tự tìm từng xe trong toàn cảnh. ROI là vị trí ô đỗ cố định do người vận hành khai báo. Web hiện chưa có công cụ kéo vẽ/lưu ROI.

## API

| Endpoint | Request | Công dụng |
|---|---|---|
| `GET /health` | — | Gateway sẵn sàng; không chứng minh ESP32 đang online |
| `GET /api/status` | — | Model, threshold, execution targets, số ROI |
| `GET /api/rois` | — | ROI hiện tại, không trả snapshot URL |
| `POST /api/predict` | Multipart `file`, query `target`, `model` | Một ảnh ô đỗ |
| `POST /api/predict-frame` | Multipart `file`, query `target`, `model` | Frame toàn cảnh và các ROI |
| `POST /api/predict-camera` | Query `target` | Lấy HTTP snapshot rồi xử lý các ROI |

`target` mặc định là `esp32`; dùng `target=backend` khi chủ động test tham chiếu trên máy tính. Không có fallback tự động từ ESP32 sang backend.

Khi có `--esp32-url`, gateway mặc định không nạp/chạy TensorFlow trên PC; chỉ xử lý ảnh và truyền tensor. Nếu cần đối chiếu cả hai nơi trong cùng service, thêm `--enable-reference`. Khi không cấu hình ESP32, service tự bật chế độ backend tham chiếu để test.

Gateway chỉ dùng ESP32 có thể cài `backend/requirements.txt` (không có TensorFlow). Chế độ backend tham chiếu và các bài test tích hợp dùng `backend/requirements-reference.txt` hoặc `backend/requirements-test.txt`.

Ví dụ PowerShell:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/predict?target=backend&model=int8" -F "file=@D:/images/slot.jpg"
curl.exe -X POST "http://127.0.0.1:8000/api/predict-frame?target=esp32&model=int8" -F "file=@D:/images/full_parking.jpg"
curl.exe -X POST "http://127.0.0.1:8000/api/predict-camera?target=esp32"
```

Trong Swagger: mở endpoint → Try it out → chọn target/model/file → Execute. Postman dùng Body → form-data → key `file` kiểu File; không đặt Content-Type thủ công.

### Response ảnh một ô

- `label`: 1 có xe, 0 không có xe.
- `car_score`, `threshold`: điểm và ngưỡng dùng phân loại.
- `execution_target`: ESP32 hay backend tham chiếu.
- `request_id`, `slot_id`, `model_sha256`: định danh giao dịch/model.
- `input_preview`: PNG data URL ảnh xám 64×64.
- `latency_ms`: thời gian Invoke trên thiết bị được chọn, không gồm truyền mạng/preprocessing.

### Response toàn cảnh

Có `camera_id`, `frame_id`, `complete`, `counts` và `results` cho từng ô. Ô thành công có `status: ok`, label/score/preview. Ô lỗi có `status: unknown`, `label: null`, `error`. Frame có lỗi vẫn trả HTTP 200 để hiển thị kết quả từng ô, nhưng `complete: false`. Không cộng các ô UNKNOWN vào số ô trống.

### Ngưỡng và model

```powershell
.\.venv\Scripts\python.exe -m backend.app --model-dir ai_model\output\run_gpu01 --threshold 0.75 --port 8000
```

Ưu tiên ngưỡng CLI, rồi báo cáo `<model-dir>/validation/metrics.json`, cuối cùng 0.75 mặc định. Gateway truyền cùng ngưỡng sang ESP32. Header firmware phải được xuất từ đúng `.tflite` của thư mục model; khác SHA-256 sẽ bị từ chối. Kiểm tra khớp hash không thay thế đo sai khác điểm giữa TFLite desktop và TFLite Micro trên board thật.

### Camera

`snapshot_url` hỗ trợ HTTP(S) trả ảnh. Chưa hỗ trợ RTSP/ONVIF hoặc vòng lặp tự lấy frame. Nếu camera chỉ có RTSP, cần adapter lấy frame bổ sung; không truyền RTSP trực tiếp cho ESP32. Camera mất kết nối trả lỗi, không tạo kết quả trống.

### Mã lỗi

- 400: chọn float cho ESP32 hoặc model không khả dụng.
- 409: chưa cấu hình ROI/snapshot.
- 413: ảnh quá 10 MB.
- 422: file/parameter/ROI không hợp lệ hoặc tỷ lệ frame không khớp cấu hình.
- 502: không có phản hồi ESP32 hợp lệ hoặc không lấy được ảnh camera.
- 503: chọn ESP32 nhưng chưa cấu hình địa chỉ.
- 500: lỗi suy luận backend.

Chạy Uvicorn trực tiếp với cấu hình mặc định: `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000` từ thư mục gốc project. Khi cần IP ESP32 hoặc cấu hình riêng, dùng CLI `python -m backend.app ...`.

Tài liệu: [kiến trúc](system_architecture.md), [train/test](training_and_evaluation.md), [FastAPI UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/).
