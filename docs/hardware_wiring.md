# Sơ Đồ Đấu Nối Phần Cứng (Hardware Wiring Diagram)

Hệ thống giám sát ô đỗ xe TinyML kết hợp vi điều khiển **ESP32-CAM (AI-Thinker)** với cảm biến khoảng cách siêu âm **HC-SR04** (hoặc ToF VL53L0X).

---

## 1. Bảng Chân Đấu Nối (Pinout Mapping)

| Module | Chân Linh Kiện | Chân ESP32-CAM | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Nguồn** | 5V | **5V** | Cần nguồn rời 5V - tối thiểu 2A |
| **Nguồn** | GND | **GND** | Nối chung mass (Common Ground) |
| **HC-SR04** | VCC | **5V** | HC-SR04 yêu cầu 5V để phát xung chuẩn |
| **HC-SR04** | Trig | **GPIO 13** | Xung kích hoạt 10µs từ ESP32 |
| **HC-SR04** | Echo | **GPIO 12** | **BẮT BUỘC** qua cầu phân áp 5V &rarr; 3.3V |
| **HC-SR04** | GND | **GND** | Mass chung |

> [!WARNING]
> **Chân Echo của HC-SR04 xuất mức logic 5V!** Chân GPIO của ESP32-CAM chỉ chịu được tối đa 3.3V. Đấu trực tiếp 5V vào GPIO 12 sẽ làm hỏng chip ESP32. Bắt buộc dùng 2 điện trở tạo cầu phân áp:
> - $R_1 = 1k\Omega$ (nối từ chân Echo tới GPIO 12)
> - $R_2 = 2k\Omega$ (hoặc $1.8k\Omega \sim 2.2k\Omega$, nối từ GPIO 12 xuống GND)
> - Điện áp tại GPIO 12 = $5V \times \frac{2k}{1k + 2k} \approx 3.33V$ (An toàn tuyệt đối).

---

## 2. Lưu Ý Về Chân Trên ESP32-CAM

ESP32-CAM có số lượng chân GPIO ngoài rất hạn chế do hầu hết chân đã dùng cho Camera OV2640 và Flash LED:
- **GPIO 0**: Dùng cho XCLK camera. Khi nạp firmware bằng mạch USB-UART (FT232RL), nối GPIO 0 xuống GND để vào chế độ Flash Mode. Khi chạy bình thường, tháo dây GPIO 0 ra.
- **GPIO 4**: Đèn Flash LED công suất cao (sáng chói). Trong code đã cấu hình bật chớp nhẹ 30ms khi chụp ảnh nếu thiếu sáng.
- **GPIO 33**: Đèn LED đỏ nhỏ mặt sau (kích hoạt mức LOW). Dùng làm chỉ báo trạng thái có xe.
- **GPIO 12 & 13**: Chân tín hiệu HS2 data của thẻ nhớ SD. Do mô hình TFLite Micro được nhúng trực tiếp vào Flash vi điều khiển, ta không dùng thẻ nhớ ngoài nên 2 chân này được tái sử dụng hoàn toàn cho Trig và Echo của cảm biến siêu âm.

---

## 3. Sơ Đồ Cấp Nguồn Ổn Định

Khi ESP32-CAM vừa bật WiFi truyền MQTT, vừa đánh thức Camera OV2640, dòng tức thời (peak current) có thể vọt lên tới **350mA - 450mA**. Nếu dùng nguồn cổng USB máy tính yếu hoặc dây cáp kém chất lượng, ESP32 sẽ bị sụt áp (Brownout Reset).

**Khuyến nghị giải pháp:**
- Dùng module nguồn MB102 cắm breadboard hoặc củ sạc 5V 2A riêng.
- Hàn thêm 1 tụ hóa $100\mu F - 470\mu F$ và 1 tụ gốm $100nF$ song song giữa 2 chân **5V** và **GND** sát ESP32-CAM để lọc xung dòng khởi động camera.
