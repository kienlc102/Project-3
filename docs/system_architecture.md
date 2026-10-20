# Kiến trúc camera góc rộng và ESP32

## Phân chia trách nhiệm

| Thành phần | Trách nhiệm |
|---|---|
| Camera cố định góc rộng | Cung cấp ảnh toàn cảnh bãi xe |
| FastAPI gateway trên PC/mini PC | Nhận ảnh, crop ROI theo cấu hình, tiền xử lý, gửi từng tensor tới ESP32 |
| ESP32 thường, ví dụ ESP32 DevKit/WROOM | Chạy model CNN INT8 bằng TFLite Micro, trả điểm và nhãn cho từng ROI |
| Dashboard | Upload để test và hiển thị kết quả từng ô, thể hiện rõ thiết bị suy luận |
| PC/GPU train | Huấn luyện float, PTQ INT8 và xuất trọng số cho firmware |

Không nối camera IP vào chân ESP32. Không gửi video HD hoặc JPEG toàn cảnh đến ESP32. Mỗi request chỉ chứa `64×64×1 = 4096` byte grayscale uint8. Backend xử lý các ROI tuần tự để một ESP32 không phải giữ nhiều ảnh cùng lúc.

Luồng triển khai sử dụng `target=esp32`. `target=backend` là chế độ tham chiếu được chọn rõ ràng để kiểm tra khi chưa có thiết bị; không tự thay thế ESP32 khi thiết bị lỗi.

## Cấu hình ROI

Copy `config/parking.example.json` thành `config/parking.json`, chỉnh tọa độ theo vị trí camera thực tế. File mẫu không tự được kích hoạt vì các tọa độ chỉ minh họa. File cấu hình thật được bỏ qua bởi Git.

- Tọa độ theo độ phân giải `reference_width × reference_height`.
- `x,y` là góc trái trên, `width,height` là kích thước ROI.
- Khi độ phân giải thay đổi nhưng cùng tỷ lệ khung hình, tọa độ được scale.
- Tỷ lệ khung hình khác quá 1% bị từ chối; cần hiệu chỉnh lại ROI.
- Nếu camera thay đổi góc/zoom/vị trí, cần cập nhật cấu hình.
- `snapshot_url` chỉ dùng cho HTTP(S) snapshot. Chưa có adapter RTSP, ONVIF hay vòng lặp lấy frame tự động.

Model hiện train bằng center crop hình vuông và bilinear resize. Backend tiếp tục dùng cùng preprocessing. Chọn ROI đủ vuông và chứa trọn xe để tránh center crop cắt mất xe. Chưa có ROI đa giác, hiệu chỉnh phối cảnh, padding hoặc sửa méo fisheye. Muốn đổi preprocessing phải đánh giá lại và có thể cần train lại.

## Giao thức gateway → ESP32

`POST http://<esp32-ip>/infer`

| Thành phần | Giá trị |
|---|---|
| Content-Type | `application/octet-stream` |
| Body | Chính xác 4096 byte grayscale uint8, thứ tự theo hàng |
| `X-Slot-Id` | ID ô đỗ, chữ/số/gạch ngang/gạch dưới |
| `X-Request-Id` | ID frame/request, dùng ghép đúng phản hồi |
| `X-Model-Sha256` | Hash file `.tflite`, phải khớp header nạp trên ESP32 |
| `X-Threshold` | Ngưỡng đã chọn trên validation hoặc cấu hình |

ESP32 tự lượng tử hóa pixel bằng scale/zero-point của input tensor, gọi `Invoke()`, giải lượng tử output sigmoid và so sánh ngưỡng. Không chia thêm 255 vì model đã chứa Rescaling.

Response chứa `request_id`, `slot_id`, `model_sha256`, `car_score`, `label`, `threshold`, `latency_ms`. Backend kiểm tra các giá trị tương ứng trước khi hiển thị. Không có giá trị hợp lệ thì ô ở trạng thái `unknown`, `label: null`, không phải nhãn 0.

`GET /health` trên ESP32 cho biết model đã khởi tạo và hash hiện tại. Địa chỉ ESP32 cấu hình bằng `--esp32-url`; chưa có tự tìm thiết bị, MQTT hay cơ chế xác thực cho triển khai mạng công cộng. Dùng mạng LAN thử nghiệm.

## Sơ đồ

README chứa sơ đồ kiến trúc và **SSD (System Sequence Diagram)** của một lượt kiểm tra. File Mermaid tương ứng:

- [Kiến trúc thành phần](diagrams/system_architecture.mmd)
- [SSD](diagrams/system_sequence.mmd)

SSD mô tả tương tác tại biên Web/Gateway với người dùng, camera và node suy luận. Bước crop bên trong gateway được ghi chú để làm rõ dữ liệu truyền sang ESP32. SSD ở đây không phải mô hình object detection Single Shot Detector; CNN vẫn phân loại từng ROI cố định.

## Trạng thái triển khai và giới hạn

- Đã có gateway upload ảnh đơn, ảnh toàn cảnh theo ROI và lấy HTTP snapshot theo yêu cầu.
- Đã có transport gửi tensor đến ESP32, kiểm tra hash/request/slot/threshold và xử lý UNKNOWN.
- Đã có firmware ESP32 HTTP/TFLite Micro và header từ model `run_gpu01`.
- Test Python có thể dùng thiết bị HTTP giả để xác minh giao thức. Điều này không chứng minh firmware đã chạy trên chip thật.
- Môi trường hiện chưa có Arduino toolchain/TFLite Micro board package để compile firmware; cần chọn thư viện TFLM tương thích và kiểm tra thực tế trên board.
- Arena ban đầu là 160 KiB, không phải số đo đã xác nhận. ESP32 thường hạn chế SRAM; cần kiểm tra `AllocateTensors()`, heap còn lại và độ trễ khi Wi-Fi hoạt động. Nếu không đủ, cần giảm kiến trúc hoặc dùng board có bộ nhớ phù hợp.
- Chưa đo FPS tổng cho N ô, latency trên ESP32, độ chính xác camera góc rộng thực tế hoặc mức điện năng. Không kế thừa các con số tiết kiệm pin của thiết kế camera/cảm biến cũ.
