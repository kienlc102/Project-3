# Phân Tích Cơ Chế Sensor Fusion & Tiết Kiệm Năng Lượng (Wake-on-Sensor)

Dự án áp dụng triết lý **Asymmetric Sensor Fusion** (Kết hợp cảm biến bất đối xứng) giữa một cảm biến tiêu thụ cực thấp (Siêu âm / ToF) và một bộ cảm biến tiêu thụ năng lượng cao (Camera + AI).

---

## 1. So Sánh Mức Tiêu Thụ Điện Năng

### Phương pháp Truyền thống (Camera Always-ON)
- Camera chụp liên tục 1 frame/giây hoặc chạy stream video.
- Dòng điện trung bình duy trì: $I_{trad} \approx 180mA - 220mA$.
- Pin Lithium 18650 dung lượng $2500mAh$ chỉ duy trì được:
  $$T_{trad} = \frac{2500mAh}{200mA} \approx 12.5 \text{ giờ (chưa đầy nửa ngày)}$$

### Phương pháp Dự án (Wake-on-Sensor Fusion)
- **Trạng thái Chờ (IDLE - 95% thời gian):**
  - Camera OV2640 ở trạng thái Sleep / PWDN.
  - Vi điều khiển chạy ở xung nhịp thấp hoặc Light Sleep, chỉ thức dậy mỗi 250ms để phát xung siêu âm (khoảng 15ms).
  - Dòng tiêu thụ trung bình: $I_{idle} \approx 14.5mA$.
- **Trạng thái Xác minh AI (ACTIVE - 5% thời gian):**
  - Khi có vật thể che chắn ($d < 15cm$), camera thức dậy chụp 1 frame và chạy TFLite Micro trong $\sim 42ms$.
  - Dòng tiêu thụ: $I_{active} \approx 180mA$ trong vòng 200ms.
- **Trạng thái Xe rời bãi (Asymmetric Reset):**
  - Khi xe rời đi, khoảng cách tăng xa ($d > 18cm$). Cảm biến siêu âm xác nhận ngay lập tức, chuyển về trạng thái TRỐNG **mà không cần bật Camera hay chạy AI**.

Dòng tiêu thụ trung bình thực tế:
$$I_{avg} = (0.95 \times 14.5mA) + (0.05 \times 180mA) \approx 22.7mA$$

**Thời gian sử dụng pin tăng vọt:**
$$T_{fusion} = \frac{2500mAh}{22.7mA} \approx 110 \text{ giờ (gần 5 ngày liên tục, tiết kiệm ~88% điện năng)}$$

---

## 2. Máy Trạng Thái Hữu Hạn (FSM Diagram)

```
        +-------------------------------------------------------+
        |                                                       |
        v                                                       |
 [STATE_IDLE_VACANT]                                            |
 (Camera TẮT, Đọc d mỗi 250ms)                                  |
        |                                                       |
        | Khoảng cách d < 15cm                                  |
        v                                                       |
 [STATE_VERIFYING_CAMERA]                                       |
 (Bật Camera, Chụp 1 ảnh 64x64,                                 |
  Chạy INT8 CNN Inference)                                      |
        |                                                       |
        +------------------------------+                        |
        |                              |                        |
  Xác suất Xe >= 0.75            Xác suất Xe < 0.75             |
        |                              |                        |
        v                              v                        |
 [STATE_OCCUPIED_MONITORING]    [Không phát hiện xe]        |
 (Đang có ô tô đỗ)              (Nhãn 0, Vẫn Xanh)       |
        |                              |                        |
        | Khoảng cách d > 18cm         +------------------------+
        | (Xe rời bãi)
        |
        +------> [KHÔNG BẬT AI] Chuyển ngay về STATE_IDLE_VACANT
```

---

## 3. Quy ước nhãn CNN: Có xe / Không có xe

- **1 (`occupied`)**: ảnh ô đỗ có xe.
- **0 (`vacant`)**: ảnh ô đỗ không có xe.
- Đầu vào là ảnh một ô đỗ grayscale 64×64; đầu ra sigmoid là điểm số có xe.
- Điểm >= 0.75: xác nhận có xe. Điểm < 0.75: giữ VACANT, gửi `NO_CAR_DETECTED`. Ngưỡng cần được hiệu chỉnh trên validation.

Có thể dùng CNRPark hoặc PKLot để train và đánh giá. Nhãn không có xe không đồng nghĩa với nhận diện người/tay. Muốn kiểm chứng khả năng loại bỏ vật cản, cần bổ sung và đánh giá dữ liệu tương ứng.

Cảm biến khoảng cách vẫn đảm nhận kích hoạt camera và phát hiện xe rời đi theo logic firmware. Việc chọn hai nhãn không tự quyết định lịch bật camera hay bảo đảm kích thước model; các thông số bộ nhớ, độ trễ và năng lượng phải được đo trên thiết bị.
