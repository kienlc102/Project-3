# Kết hợp đo khoảng cách và nhận diện xe

Đây là thiết kế hệ thống đích: **camera góc rộng + cảm biến khoảng cách theo từng ô + ESP32 thường chạy CNN INT8 và fusion**. Camera nằm ngoài ESP32. CNN phân loại ảnh một ô; cảm biến đo sự hiện diện của vật thể. Hai nguồn được kết hợp để quyết định trạng thái đỗ xe.

**Trạng thái triển khai:** gateway và firmware hiện có mới thực hiện nhánh ảnh/CNN. Chưa có driver đo khoảng cách, bộ lọc, giao thức fusion hoặc hiển thị hai nguồn trên web. Các trường và luồng bổ sung dưới đây là đặc tả cần triển khai, không phải API đang chạy.

## Ghép cảm biến với ô đỗ

- Mỗi ô có một ROI và một cảm biến khoảng cách riêng, ví dụ HC-SR04 cho sa bàn. Một cảm biến đặt ở cổng không thể cho biết trạng thái của tất cả các ô.
- Dùng cùng `slot_id` từ ROI đến cảm biến trên ESP32; ví dụ `slot_01` ↔ ROI 1 ↔ cảm biến 1. Phải kiểm tra ánh xạ bằng cách đặt vật thể lần lượt vào từng ô.
- Một ESP32 có thể phục vụ vài ô nếu đủ GPIO, thời gian xử lý và bộ nhớ. Khi mở rộng nhiều node, cần thêm ánh xạ `slot_id → node_id → sensor_id`; gateway hiện chỉ cấu hình một địa chỉ ESP32.
- Vị trí và hướng cảm biến phải tạo được khác biệt rõ giữa ô trống và ô có xe. Vật thể ngoài ô, người đi qua hoặc xe ở ô bên cạnh có thể làm sai số đo.

## Vai trò của hai nguồn

| Nguồn | Cung cấp | Hạn chế |
|---|---|---|
| Khoảng cách | Có vật thể trong vùng đo hay không | Không xác nhận vật thể là xe |
| CNN trên ROI | Điểm nhận diện xe trong ảnh | Có thể nhầm bóng đổ, ánh sáng, che khuất |
| Fusion trên ESP32 | Quyết định cuối cùng theo từng ô | Cần hai nguồn hợp lệ và gần nhau về thời gian |

Không đưa khoảng cách trực tiếp vào CNN hiện tại. Giữ nguyên input `64×64×1`, nhãn train `1 = có xe`, `0 = không có xe`. Fusion là logic sau suy luận, không cần train lại chỉ để bổ sung cảm biến. Tuy nhiên vẫn cần kiểm thử toàn hệ thống trên sa bàn.

## Lọc khoảng cách và chống dao động

1. Đọc từng cảm biến tuần tự; bố trí chu kỳ đo để tránh các cảm biến siêu âm gây nhiễu chéo. Chu kỳ và timeout phải chọn theo module thực tế.
2. Loại số đo timeout, ngoài dải hợp lệ hoặc lỗi. **Không có echo không đồng nghĩa ô trống.** Chỉ lọc trung vị trên mẫu còn mới và hợp lệ; không dùng lại mẫu cũ vô thời hạn.
3. Hiệu chỉnh hai ngưỡng theo từng ô: `D_enter < D_exit`. Khoảng cách nhỏ hơn `D_enter` là ứng viên có vật thể; lớn hơn `D_exit` là ứng viên trống.
4. Yêu cầu nhiều mẫu hợp lệ liên tiếp để xác nhận chuyển trạng thái, ví dụ 3 mẫu lúc bắt đầu thử nghiệm. Mẫu lỗi làm hủy chuỗi xác nhận. Khi nằm giữa hai ngưỡng, giữ trạng thái cảm biến đã xác nhận nếu dữ liệu còn hợp lệ; lúc khởi động chưa có trạng thái thì là `unknown`.
5. Đặt thời hạn dữ liệu cảm biến và độ lệch thời gian tối đa giữa frame và số đo. Có thể bắt đầu thử ở 1 giây rồi điều chỉnh sau khi đo latency; đây không phải thông số đã kiểm chứng. Nếu chờ CNN quá lâu, phải đọc lại khoảng cách và/hoặc lấy frame mới.

Với cách lắp mà xe làm khoảng cách giảm, ví dụ **sa bàn** có thể bắt đầu thử `D_enter = 15 cm`, `D_exit = 18 cm`. Chỉ dùng khi đo thực tế cho thấy hai khoảng này phân biệt được xe và ô trống; không áp dụng trực tiếp cho bãi xe thật. Nếu cách lắp tạo quan hệ khác, phải đổi quy tắc phân loại khoảng cách tương ứng.

## Quy tắc quyết định cuối cùng

Chọn quy tắc hai nguồn đồng thuận cho phiên bản đầu để dễ giải thích và kiểm tra:

| Cảm biến đã lọc, còn mới | CNN hợp lệ | Trạng thái cuối | Lý do |
|---|---|---|---|
| Có vật thể | Có xe: `car_score >= threshold` | `1 / occupied` | Hai nguồn xác nhận có xe |
| Trống | Không có xe: `car_score < threshold` | `0 / vacant` | Hai nguồn xác nhận trống |
| Có vật thể | Không có xe | `unknown` | Có thể là vật cản hoặc CNN bỏ sót |
| Trống | Có xe | `unknown` | Có thể cảm biến lệch hướng hoặc CNN nhận nhầm |
| Lỗi, thiếu, quá hạn hoặc chưa ổn định | Bất kỳ | `unknown` | Chưa có đủ bằng chứng |
| Bất kỳ | Thiếu ảnh, lỗi model, timeout hoặc frame quá cũ | `unknown` | Chưa có đủ bằng chứng |

`unknown` dùng `label: null`, không tính vào số ô trống. Có thể lưu trạng thái hợp lệ trước đó để tham khảo kèm thời điểm, nhưng không trình bày như trạng thái hiện tại đã được xác nhận. Mâu thuẫn cần đo/lấy ảnh lại; không mặc định ưu tiên một nguồn.

Khoảng cách có thể kích hoạt một lượt kiểm tra ảnh khi có thay đổi. Vẫn cần kiểm tra định kỳ cả hai nguồn, bao gồm ô đang trống, để phát hiện lỗi cảm biến. Không deep sleep ESP32 khi gateway còn cần gọi HTTP; thiết kế hiện chưa có cơ chế đánh thức và đồng bộ mạng.

## Luồng triển khai cần bổ sung

1. ESP32 đọc cảm biến, lọc và lưu trạng thái theo `slot_id`.
2. Gateway lấy frame mới từ camera, crop ROI và gửi 4096 byte đến ESP32 kèm ID giao dịch/ô và hash model.
3. ESP32 chạy CNN, lấy mẫu khoảng cách tương ứng, kiểm tra độ mới rồi fusion. Lỗi một nguồn cho kết quả `unknown`.
4. ESP32 trả riêng bằng chứng CNN, bằng chứng khoảng cách và kết quả cuối; gateway kiểm tra định danh rồi hiển thị trên dashboard.

**Response fusion dự kiến** cần có `cnn_label`, `car_score`, `distance_cm` (null khi lỗi), `distance_state`, `sensor_id`, tuổi mẫu đo/độ lệch với frame, `fusion_status`, `fusion_reason` và `label` cuối cùng. Định dạng giao thức và cách đồng bộ thời gian giữa gateway/ESP32 phải được triển khai, kiểm thử trước khi bật luồng này. Không so trực tiếp đồng hồ uptime của ESP32 với giờ máy tính.

Upload ảnh lưu từ trước chỉ kiểm tra CNN. Không ghép ảnh cũ với khoảng cách đang đo để công bố trạng thái bãi xe hiện tại. Test fusion cần frame và khoảng cách cùng lượt đo, hoặc bộ dữ liệu kiểm thử đã ghi hai nguồn cùng thời điểm.

## Kiểm thử sau khi triển khai

| Tình huống | Kết quả mong đợi |
|---|---|
| Ô trống, cả ảnh và khoảng cách xác nhận trống | `0` |
| Đặt xe vào ô, đủ mẫu xác nhận và CNN nhận xe | `1` |
| Đặt vật cản không phải xe | `unknown` nếu cảm biến có vật nhưng CNN không nhận xe |
| Hai nguồn bất đồng | `unknown`, lưu lý do và thử lại |
| Dao động quanh ngưỡng | Không chuyển trạng thái cảm biến liên tục |
| Rút cảm biến, không echo hoặc dữ liệu quá hạn | `unknown`, không biến thành ô trống |
| Camera mất kết nối, sai hash model hoặc ESP32 lỗi | Lỗi/`unknown`, không biến thành ô trống |
| Đổi chéo cảm biến hoặc ROI | Phát hiện ánh xạ sai khi thử từng ô |
| Upload ảnh cũ | Chỉ báo kết quả CNN, không xác nhận fusion thời gian thực |

Đánh giá cả tỷ lệ kết luận sai và tỷ lệ `unknown`; quy tắc đồng thuận có thể làm tăng số ô chưa xác định. Chưa có số đo chứng minh fusion cải thiện độ chính xác của project này.
