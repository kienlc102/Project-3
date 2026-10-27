# Parkly — Frontend quản lý bãi đỗ xe

Giao diện Next.js 16 / React 19 trong `frontend/`, dùng App Router và TypeScript.

## Chạy toàn bộ bằng Docker Compose

Bật Docker Desktop (Linux containers), bảo đảm model đã có tại
`ai_model/output/run_gpu01`, rồi chạy từ thư mục gốc project:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f frontend
```

- Giao diện chủ bãi: http://localhost:3000
- API và Swagger: http://localhost:8000/docs

Frontend dùng bản build production standalone và chỉ khởi động khi backend
healthy. Next.js chuyển tiếp API đến `http://backend:8000` qua mạng nội bộ
Compose; trình duyệt gọi `/gateway/*` cùng origin với frontend.
Image không cần Node.js cài trên máy host.

Đổi cổng giao diện bằng `FRONTEND_PORT` trong file `.env` ở gốc project
(ví dụ `FRONTEND_PORT=3001`), rồi chạy lại `docker compose up -d`.
`frontend/.env.local` không được đưa vào image; địa chỉ backend Docker
được truyền khi build qua `build.args.BACKEND_URL` trong `compose.yaml`.

Sau khi sửa mã frontend, chạy `docker compose up --build -d frontend`.
Dừng toàn bộ: `docker compose down`.
Mặc định giao diện vẫn mở ở chế độ minh họa; bấm **Kết nối hệ thống thật**
để dùng API từ container backend. Thiếu cấu hình ROI thì chưa có sơ đồ thật.

## Chạy tại máy

Mở backend ở cổng 8000 bằng Docker Compose hoặc CLI hiện có, rồi chạy:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Truy cập http://localhost:3000. Trên Windows, `npm.cmd` chạy được cả khi
PowerShell chặn script `npm.ps1`. Có thể dùng `npm` trong Command Prompt.

Mặc định trang mở ở **chế độ minh họa** với dữ liệu cố định có nhãn DEMO.
Bấm **Kết nối hệ thống thật** để đọc API của backend. Khi backend lỗi hoặc
chưa có kết quả, trạng thái ô đỗ là **chưa xác định**, không tự chuyển thành ô trống.

## Kết nối backend

Next.js chuyển tiếp `/gateway/*` đến `/api/*` trên backend để trình duyệt
không cần gọi API khác origin. Mặc định dùng `http://127.0.0.1:8000`.
Đổi backend bằng cách sao chép `frontend/.env.example` thành
`frontend/.env.local`, sửa `BACKEND_URL`, rồi khởi động lại Next.js.

```dotenv
BACKEND_URL=http://127.0.0.1:8000
```

Biến này được đọc khi khởi động dev/build. Với production, cấu hình biến
trước `npm.cmd run build`.

Backend cần model hợp lệ để khởi động. Sơ đồ thật lấy danh sách ô từ
`config/parking.json`. Kiểm tra camera cần `snapshot_url` hợp lệ;
upload ảnh dùng API `predict-frame`, cũng cần cấu hình ROI phù hợp.
Chọn ESP32 hoặc backend tham chiếu trong **Camera & thiết bị**, tùy
theo chế độ backend đang bật.

## Các màn hình

- **Tổng quan:** số ô, mức sử dụng, sơ đồ tương tác, số lượt kiểm tra theo giờ.
- **Quản lý ô đỗ:** tìm mã ô, lọc trạng thái, xem chi tiết, xuất kết quả CSV.
- **Camera & thiết bị:** trạng thái cấu hình, nơi thực thi, kiểm tra snapshot hoặc ảnh upload tối đa 10 MB.
- **Lịch sử kiểm tra:** tối đa 100 lần kiểm tra trong phiên; mất khi tải lại trang hoặc đổi chế độ.
- **Cài đặt:** tên hiển thị lưu tại trình duyệt; bật kiểm tra camera mỗi 30 giây khi tab đang hiển thị.

Sơ đồ là bố cục tổng hợp từ danh sách ROI, không theo tọa độ thực tế.
Kết quả phản ánh lần kiểm tra gần nhất, không phải dữ liệu liên tục được xác nhận.
Biểu đồ chế độ thật chỉ tính lượt kiểm tra trong phiên, không phải lưu lượng xe.

Backend hiện chưa hỗ trợ xác thực chủ bãi, doanh thu, biển số, CRUD cấu hình,
lưu lịch sử dài hạn hoặc kết hợp cảm biến khoảng cách. UI không giả lập các
thao tác lưu vào backend cho những tính năng này.

## Cấu trúc component

`component/parking-dashboard.tsx` ghép bố cục và các màn hình con.
Các phần triển khai nằm trong `component/parking-dashboard/`:

- `use-parking-dashboard.ts`: state, gọi API, kiểm tra camera, upload, lịch sử và xuất CSV.
- `types.ts`, `data.ts`, `api.ts`, `format.ts`: kiểu dữ liệu, dữ liệu minh họa, HTTP client và định dạng thời gian.
- `sidebar.tsx`, `dashboard-header.tsx`, `page-heading.tsx`, `dashboard-footer.tsx`: bố cục chung.
- `metrics.tsx`, `parking-map.tsx`, `parking-slot.tsx`, `capacity-card.tsx`, `quick-actions.tsx`: thống kê và sơ đồ.
- `activity-panel.tsx`, `activity-chart.tsx`, `system-summary.tsx`: hoạt động và trạng thái hệ thống.
- `slots-table.tsx`, `devices-panel.tsx`, `history-panel.tsx`, `settings-panel.tsx`: các màn hình quản lý.
- `status-badge.tsx`, `slot-dialog.tsx`: trạng thái ô đỗ và hộp thoại chi tiết.

JSX dùng thụt lề 2 dấu cách, các thẻ con xuống dòng theo cấu trúc lồng nhau.
Định dạng lại hoặc kiểm tra định dạng từ thư mục `frontend`:

```powershell
npm.cmd run format
npm.cmd run format:check
```

## Build production

```powershell
cd frontend
npm.cmd run build
npm.cmd run start
```

Compose chạy cả frontend và backend; các lệnh trên dành cho chạy frontend ngoài Docker.
