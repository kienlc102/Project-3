# Kịch Bản Thuyết Trình Demo 4 Pha Trên Sa Bàn (Diorama Script)

Tài liệu này được biên soạn để hỗ trợ bạn trình diễn trước hội đồng chấm thi, giảng viên hướng dẫn hoặc khách hàng.

---

## Chuẩn Bị Sa Bàn (Diorama Setup)
1. **Mô hình sa bàn:** 1 ô đỗ xe kẻ vạch trắng, gắn cụm ESP32-CAM và cảm biến siêu âm HC-SR04 hướng từ trên cao (hoặc chéo 45 độ) xuống mặt sàn.
2. **Đạo cụ:**
   - 1 xe ô tô đồ chơi (tỷ lệ 1:24 hoặc 1:32).
   - Bàn tay của bạn hoặc tượng người nhỏ (lego / mô hình người).
3. **Màn hình hiển thị:** Mở Web Dashboard trên trình duyệt (`d:/Project-3/dashboard/index.html`).

---

## 4 Pha Trình Diễn Chi Tiết

### 🟢 Pha 1: Trạng Thái Cơ Sở (Baseline Standby)
- **Hành động:** Để ô đỗ trống hoàn toàn. Không chạm vào sa bàn.
- **Lời thuyết trình:**
  > *"Kính thưa thầy/cô, ở trạng thái ban đầu khi ô đỗ hoàn toàn trống, cảm biến khoảng cách đo được cự ly xa (> 40cm). Hệ thống tự động đặt Camera và bộ suy luận AI vào trạng thái ngủ sâu (Sleep Mode). Dòng tiêu thụ chỉ ở mức 14.5mA. Web Dashboard hiển thị ô đỗ màu XANH với trạng thái VACANT."*

### 🟡 Pha 2: Mô phỏng vật cản không phải xe
- **Hành động:** Trên dashboard, chọn pha nhiễu. Bàn tay chỉ minh họa vật cản; điểm 0.14 là giá trị mô phỏng.
- **Lời thuyết trình:**
  > "Mô hình có hai nhãn: 1 là có xe, 0 là không có xe. Trong ví dụ mô phỏng này, cảm biến kích hoạt camera và điểm có xe dưới ngưỡng nên ô đỗ giữ trạng thái VACANT. Model không đưa ra nhãn người. Khả năng xử lý bàn tay thật cần được đánh giá bằng dữ liệu tương ứng."
- **Firmware thật:** Khi điểm có xe dưới ngưỡng, gửi `reason: NO_CAR_DETECTED`.

### 🔴 Pha 3: Đỗ Xe Ô Tô Thật Sự (Vehicle Occupancy)
- **Hành động:** Đẩy xe ô tô đồ chơi vào đỗ đúng giữa ô đỗ xe.
- **Lời thuyết trình:**
  > *"Tiếp theo, một chiếc ô tô tiến vào đỗ. Cảm biến siêu âm ghi nhận vật cản ở cự ly 8cm (< 15cm) và đánh thức Camera. Mô hình CNN trích xuất đặc trưng hình học của xe qua 3 khối Depthwise Separable Conv, trả về độ tin cậy đạt 94% (vượt xa ngưỡng 75%). Hệ thống phát bản tin MQTT xác nhận ô đỗ có xe. Web Dashboard lập tức đổi màu sang ĐỎ (OCCUPIED) và đèn LED chỉ báo trên vi điều khiển sáng lên."*

### 🟢 Pha 4: Xe Rời Bãi (Tiết Kiệm Điện Năng Đột Phá - Zero-AI Departure)
- **Hành động:** Nhấc xe ô tô ra khỏi ô đỗ.
- **Lời thuyết trình:**
  > *"Cuối cùng, khi xe rời đi, khoảng cách đo được lập tức nhảy về trên 45cm. Tại thời điểm này, theo thuật toán Asymmetric Fusion, hệ thống khẳng định ô đỗ đã trống mà KHÔNG CẦN PHẢI BẬT CAMERA HAY CHẠY LẠI MÔ HÌNH AI. Trạng thái ô đỗ trên Dashboard chuyển ngay về màu XANH. Nhờ thiết kế loại bỏ suy luận AI khi xe rời bãi, hệ thống tiết kiệm được thêm 50% số lần đánh thức camera, giúp kéo dài thời lượng pin lên đến hàng tuần."*
