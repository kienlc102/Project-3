# Smart Parking

Project cá nhân giám sát ô đỗ xe: FastAPI, giao diện Next.js, CNN TinyML
và YOLO nhận diện ô tô từ camera góc cao. CNN chạy trên PC hoặc ESP32;
YOLO hiện chạy trên CPU. Driver cảm biến khoảng cách và sensor fusion chưa có.

## Chạy bằng Docker

Bật Docker Desktop ở chế độ Linux containers, chạy từ thư mục gốc:

```powershell
docker compose up --build -d
```

- Giao diện quản lý: http://localhost:3000 — bấm **Kết nối hệ thống thật**.
- Trang test ảnh: http://localhost:8000/
- Swagger: http://localhost:8000/docs
- Trạng thái model: http://localhost:8000/api/status

Compose bật cả CNN tham chiếu INT8/Float32 và YOLO. Cần có sẵn model:

```text
ai_model/output/run_gpu01/parking_cnn.keras
ai_model/output/run_gpu01/parking_cnn_int8.tflite
ai_model/output/vision/geotrax_hbb_yolov8s_1920_v1.pt
```

Nếu cần đổi cấu hình, sao chép `.env.example` thành `.env` một lần rồi sửa:

```dotenv
FRONTEND_PORT=3000
BACKEND_PORT=8000
VISION_CONFIDENCE=0.75
VISION_IMAGE_SIZE=640
VISION_ROTATIONS=0,90,180,270
VISION_EDGE_MARGIN=1
ESP32_URL=
```

Các biến đường dẫn model và camera có trong `.env.example`. Để trống
`ESP32_URL` khi chưa dùng board thật; điền IP LAN của ESP32 nếu có.
Sau khi sửa `.env`, chạy `docker compose up -d` để áp dụng.

```powershell
docker compose ps
docker compose logs -f backend
docker compose down
```

Sau khi sửa mã nguồn: `docker compose up --build -d`.

## Chạy trực tiếp trên Windows

```powershell
python -m venv .venv-vision
.\.venv-vision\Scripts\python.exe -m pip install -r backend\requirements-comparison.txt
# Chuẩn bị weights YOLO nếu chưa có.
.\.venv-vision\Scripts\python.exe -m ai_model.prepare_vision_model --model parking-car
.\.venv-vision\Scripts\python.exe -m backend.app --enable-reference --vision-model parking-car
```

Mở terminal khác để chạy giao diện:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Frontend mặc định chuyển tiếp API đến `http://127.0.0.1:8000`. Đổi bằng
`BACKEND_URL` trong `frontend/.env.local` trước khi dev/build.
Chỉ chạy YOLO thì bỏ `--enable-reference`. Muốn dùng ESP32, thêm
`--esp32-url http://IP_ESP32`. Gateway không tự chuyển sang CNN trên PC khi board lỗi.

## Test nhận diện

```powershell
curl.exe -X POST "http://localhost:8000/api/detect/tinyml" -F "file=@test_image/test2-car.jpg"
curl.exe -X POST "http://localhost:8000/api/detect/yolo" -F "file=@test_image/test2.jpg"
```

API nhận multipart field `file`, hỗ trợ JPG/PNG/WebP/BMP, tối đa 10 MB.
TinyML phân loại ảnh **một ô đỗ**; YOLO trả bounding box trên toàn ảnh và chỉ đếm
lớp `car`. Thêm `?debug=true` vào API YOLO để xem nhãn từng hướng, kết quả bỏ phiếu
và lý do loại box.

YOLO mặc định confidence **0.75**, chạy bốn hướng 0/90/180/270 độ rồi đưa các box
về tọa độ ảnh gốc và gộp theo IoU. Nhãn được chọn bằng tổng confidence, tối đa
một phiếu cho mỗi lớp ở mỗi hướng; `car` cần ít nhất hai hướng đồng thuận.
Các box ứng viên dùng ngưỡng tối đa 0.35 để giữ bằng chứng phân loại. Ngưỡng cuối
vẫn là `VISION_CONFIDENCE`, áp dụng lên điểm model cao nhất của lớp thắng;
điểm tổng phiếu không phải xác suất và không thay cho confidence.

API upload mặc định bỏ box chạm mép ảnh trong khoảng 1 pixel để đếm xe hiện đầy đủ.
`test1.jpg` trả 5 ô tô (xe máy được loại theo nhãn, phần ô tô ở mép phải bị bỏ qua);
`test2.jpg` trả 2 ô tô ở cả confidence 0.35 và 0.75 trong kiểm thử local.
Đặt `VISION_EDGE_MARGIN=0` nếu muốn tính cả xe bị cắt ở mép. API theo ROI vẫn dùng
xe hiện một phần để xét ô đỗ, không áp dụng quy tắc bỏ mép của API đếm toàn ảnh.

Bốn hướng tốn bốn lượt suy luận; đặt `VISION_ROTATIONS=0` để chạy một lượt,
nhưng khi đó có thể tái hiện lỗi phân loại `car`/`truck` ở `test2.jpg`.
CLI tương ứng: `--vision-rotations 0,90,180,270 --vision-edge-margin 1`.
Chưa xác nhận chất lượng trên tập camera độc lập; `test-crop.jpg` vẫn có thể bị bỏ sót.
Confidence CNN và YOLO có ý nghĩa khác nhau.

## Camera và ESP32

Để dùng sơ đồ ô đỗ hoặc API theo camera, tạo `config/parking.json` từ
`config/parking.example.json`, chỉnh ROI và `snapshot_url` theo camera thật.
Tọa độ trong file mẫu chỉ minh họa. Khởi động lại backend sau khi sửa file:
`docker compose restart backend`.

Trong Docker, camera HTTP trên máy host dùng `host.docker.internal` thay cho
`localhost`; camera LAN dùng IP LAN. USB/CSI trên Pi có mẫu cấu hình tại
`config/parking.vision.example.json`; Docker cần thêm ánh xạ thiết bị USB hoặc
driver Picamera2 cho CSI.

Firmware ở `firmware_esp32/esp32_parking_inference/`. Sửa Wi-Fi trong
`esp32_config.h`, dùng `model_data.h` khớp model INT8 rồi nạp bằng Arduino IDE
với ESP32/TensorFlow Lite Micro tương thích. Xem IP trên Serial Monitor 115200;
kiểm tra `http://IP_ESP32/health` trước khi kết nối gateway.

## Train CNN và kiểm thử

Chuẩn bị dataset riêng theo `train/val/test`, mỗi tập có `vacant/occupied`.
Dùng môi trường Python đã cài `ai_model/requirements.txt`, rồi chạy:

```powershell
python -m ai_model.check_dataset --dataset-dir ai_model/dataset
python -m ai_model.train_and_quantize --dataset-dir ai_model/dataset --output-dir ai_model/output/run_new --epochs 40 --batch-size 32 --device cpu
```

Train vào thư mục mới để giữ model đang dùng. Nếu dùng GPU trên Windows,
chạy trong Ubuntu/WSL2 với `ai_model/requirements-gpu.txt` và `--device gpu`.
Các script trong `ai_model/` có `--help` cho chuẩn bị dữ liệu và đánh giá.

Chạy bộ kiểm thử backend:

```powershell
.\.venv-vision\Scripts\python.exe -m pip install httpx
.\.venv-vision\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

Các test dùng thiết bị/driver giả và weights local; cần kiểm chứng riêng trên
ESP32, Raspberry Pi và camera thật.
