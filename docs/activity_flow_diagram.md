# Luồng hoạt động camera góc rộng và ESP32

```mermaid
flowchart TD
    Start[Khởi động gateway với ROI và địa chỉ ESP32] --> Source{Nguồn ảnh}
    Source -->|Upload| Upload[Nhận ảnh một ô hoặc toàn cảnh]
    Source -->|HTTP snapshot theo yêu cầu| Camera[Lấy frame camera đã cấu hình]
    Upload --> Validate[Kiểm tra dung lượng, định dạng và kích thước]
    Camera --> Validate
    Validate --> Scope{Ảnh toàn cảnh?}
    Scope -->|Có| Config{Có cấu hình ROI đúng camera?}
    Config -->|Không| Reject[Từ chối, yêu cầu cấu hình ROI]
    Config -->|Có| Crop[Crop từng ROI theo độ phân giải tham chiếu]
    Scope -->|Không| Single[Dùng ảnh một ô]
    Crop --> Prep[Grayscale, center crop vuông, bilinear resize 64x64]
    Single --> Prep
    Prep --> Target{Thiết bị suy luận}
    Target -->|ESP32 triển khai| Send[Gửi 4096 byte và metadata qua HTTP]
    Target -->|Backend tham chiếu, chọn rõ| Reference[Chạy model trên PC để so sánh]
    Send --> Device{ESP32 ready và model hash đúng?}
    Device -->|Có| Infer[Lượng tử hóa input, TFLM Invoke, giải lượng tử sigmoid]
    Device -->|Không hoặc timeout| Unknown[UNKNOWN / lỗi, không gán vacant]
    Infer --> Verify{Phản hồi đúng ID, hash, threshold?}
    Verify -->|Không| Unknown
    Verify -->|Có| Score{Điểm có xe >= ngưỡng?}
    Reference --> Score
    Score -->|Có| Occupied[Nhãn 1 - Có xe]
    Score -->|Không| Vacant[Nhãn 0 - Không có xe]
    Occupied --> Result[Hiển thị kết quả từng ô]
    Vacant --> Result
    Unknown --> Result
```

Các ROI xử lý tuần tự. Nếu ESP32 lỗi ở một ROI, các ROI còn lại của frame được đánh dấu UNKNOWN thay vì tiếp tục chờ timeout lặp lại. Frame mới phải được yêu cầu lại; chưa có worker lấy video tự động hoặc cơ sở dữ liệu lịch sử.

Trạng thái trống/có xe đều được quyết định từ model cho mỗi lượt xử lý. Không còn nhánh xe rời đi chỉ dùng cảm biến hoặc cơ chế Wake-on-Sensor.

SSD có trong [README](../README.md) và [file Mermaid](diagrams/system_sequence.mmd). Kiến trúc, giao thức và giới hạn triển khai ở [system_architecture.md](system_architecture.md).
