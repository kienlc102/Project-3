# Chạy hệ thống và tự cập nhật mạng LAN

Script `start-system.ps1` đọc IP và netmask của máy host, sau đó cập nhật file
`.runtime/host-network.json` mỗi 10 giây. Backend Docker đọc thông tin này để
tìm ESP32 trong LAN khi địa chỉ IP thay đổi.

## Chuẩn bị

- Mở Docker Desktop, dùng Linux containers.
- Kết nối máy tính và ESP32 vào cùng LAN, không bật cách ly thiết bị.
- ESP32 đã được nạp firmware có mDNS và API `/health`.
- Trong `.env` ở thư mục gốc project, đặt:

```dotenv
ESP32_URL=auto
ESP32_DISCOVERY_SUBNETS=auto
```

Mở PowerShell tại thư mục gốc project:

```powershell
cd D:\Project-3
```

Nếu project nằm ở máy hoặc ổ đĩa khác, thay đường dẫn trên cho phù hợp.

## 1. Container đang chạy: chỉ theo dõi thay đổi LAN

```powershell
.\scripts\start-system.ps1 -NetworkOnly
```

Đây là chế độ dùng khi bạn chỉ cần tự cập nhật mạng host:

- Không gọi Docker Compose.
- Không build image.
- Không khởi động lại container.
- Theo dõi LAN mỗi 10 giây, kể cả khi đổi Wi-Fi.

**Giữ terminal mở trong khi sử dụng hệ thống.**

## 2. Khởi động hệ thống bằng image đã có

```powershell
.\scripts\start-system.ps1 -NoBuild
```

Chỉ khởi động backend và theo dõi LAN:

```powershell
.\scripts\start-system.ps1 -BackendOnly -NoBuild
```

Các lệnh này không yêu cầu build lại. Cần có image từ lần build trước.

## 3. Lần đầu chạy hoặc sau khi sửa code/dependencies

Build và khởi động toàn bộ hệ thống, sau đó tiếp tục theo dõi LAN:

```powershell
.\scripts\start-system.ps1
```

Chỉ build/khởi động backend:

```powershell
.\scripts\start-system.ps1 -BackendOnly
```

Docker có thể tái sử dụng các lớp build được cache; không nhất thiết cài lại
toàn bộ môi trường mỗi lần. Sau khi build, script chỉ cập nhật mạng theo chu kỳ,
không lặp lại bước build.

## 4. Kiểm tra kết quả

Script hiển thị IP/prefix của host, ví dụ:

```text
Host LAN: 192.168.1.12/24
Network-only mode: Docker containers are unchanged.
Monitoring host LAN. Keep this terminal open. Ctrl+C stops host-network updates.
```

Địa chỉ trên chỉ là ví dụ, không cần nhập vào cấu hình. Khi đổi mạng, script in
`Host LAN changed: ...`; backend sẽ tìm lại board khi mất kết nối.

Mở terminal thứ hai tại thư mục gốc để xem trạng thái:

```powershell
docker compose ps
docker compose logs -f backend
```

Kiểm tra địa chỉ ESP32 mà backend tìm được:

```powershell
curl.exe http://localhost:8000/api/status
```

Trong JSON:

- `esp32.mode`: `auto`.
- `esp32.url`: địa chỉ board đã tìm được; có thể là `null` khi chưa tìm thấy.
- `esp32.discovery_error`: thông tin lỗi nếu tìm kiếm thất bại.

Giao diện mặc định: <http://localhost:3000>.

## 5. Dừng và chạy lại

Nhấn **Ctrl+C** trong terminal chạy script để dừng theo dõi LAN. Các container
vẫn chạy. Nếu thông tin host không được cập nhật quá 45 giây, backend từ chối
dùng subnet cũ để dò HTTP; mDNS vẫn có thể hoạt động nếu mạng hỗ trợ.

Tiếp tục theo dõi mà không build lại:

```powershell
.\scripts\start-system.ps1 -NetworkOnly
```

Để dừng các container, chạy riêng:

```powershell
docker compose stop
```

## Xử lý lỗi thường gặp

### PowerShell báo không được phép chạy script

Nếu chính sách của máy cho phép, mở một tiến trình PowerShell với tùy chọn áp
dụng riêng cho lần chạy này:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-system.ps1 -NetworkOnly
```

### Backend báo thiếu hoặc hết hạn thông tin mạng host

Kiểm tra terminal chạy script còn mở và có cập nhật file hay không:

```powershell
Get-Content .runtime\host-network.json
```

Nếu container được tạo trước khi có cấu hình mount thư mục `.runtime`, cần tạo
lại backend một lần bằng `start-system.ps1 -BackendOnly`. Những lần sau có thể
dùng `-NetworkOnly`.

### Không tìm thấy ESP32

- Kiểm tra board đã kết nối Wi-Fi và Serial có `ready=1`.
- Kiểm tra máy tính và board có thể kết nối trực tiếp trong LAN.
- Kiểm tra `esp32.discovery_error` và log backend.
- Nếu có nhiều board cùng model, đặt `ESP32_URL` cụ thể để chọn board.
- Dò HTTP hiện giới hạn tối đa 1024 địa chỉ private IPv4; với subnet lớn hơn,
  cần mDNS hoặc cấu hình phạm vi dò nhỏ hơn bằng `ESP32_DISCOVERY_SUBNETS`.

Chỉ chạy **một bản script theo dõi LAN** tại một thời điểm để tránh nhiều tiến
trình cùng cập nhật file metadata.
