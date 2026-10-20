# Luồng hoạt động kết hợp khoảng cách và CNN

Sơ đồ mô tả **thiết kế đích**. Code hiện có chỉ thực hiện nhánh CNN; driver khoảng cách và fusion chưa được triển khai.

```mermaid
flowchart TD
    Start[Khởi động và kiểm tra ánh xạ ROI - slot_id - cảm biến] --> Frame[Lấy frame mới từ camera góc rộng]
    Frame --> Crop[Gateway crop từng ROI và resize grayscale 64x64]
    Crop --> Send[Gửi tensor và metadata tới ESP32]
    Send --> CNN[ESP32 chạy CNN INT8 cho ô tương ứng]
    Send --> Measure[Đọc cảm biến đúng ô, loại mẫu lỗi, lọc và hysteresis]
    CNN --> Fresh{Hai nguồn hợp lệ và đủ gần nhau về thời gian?}
    Measure --> Fresh
    Fresh -->|Không| Unknown[UNKNOWN - label null và lý do]
    Fresh -->|Có| Agree{Hai nguồn đồng thuận?}
    Agree -->|Cùng có xe và vật thể| Occupied[Nhãn 1 - Có xe]
    Agree -->|Cùng không có xe và trống| Vacant[Nhãn 0 - Không có xe]
    Agree -->|Mâu thuẫn| Unknown
    Occupied --> Result[Gateway kiểm tra phản hồi và hiển thị bằng chứng hai nguồn]
    Vacant --> Result
    Unknown --> Result
```

Mỗi ô có một cảm biến riêng. Mất echo, lỗi mạng, sai hash/ID hoặc dữ liệu quá hạn phải báo lỗi/UNKNOWN, không suy ra ô trống. Nếu chưa xác nhận trạng thái cảm biến lúc khởi động thì cũng là UNKNOWN. Chỉ giữ trạng thái trong vùng hysteresis khi dữ liệu cảm biến còn hợp lệ.

Ngưỡng khoảng cách hiệu chỉnh theo cách lắp; ngưỡng CNN chọn bằng validation. Khoảng cách có thể kích hoạt lượt kiểm tra mới khi có thay đổi, nhưng cần kiểm tra định kỳ cả hai nguồn để phát hiện lỗi. Chưa có worker camera tự động hoặc cơ chế đánh thức ESP32 trong code hiện tại.

Upload ảnh lưu từ trước là nhánh kiểm tra CNN độc lập, không ghép với khoảng cách hiện tại. Chi tiết quy tắc, đồng bộ và các ca kiểm thử: [sensor_fusion.md](sensor_fusion.md). SSD nằm trong [README](../README.md) và [file Mermaid](diagrams/system_sequence.mmd).
