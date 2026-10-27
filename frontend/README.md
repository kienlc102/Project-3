# Parkly frontend

Giao diện quản lý bãi đỗ xe bằng Next.js 16, React 19 và TypeScript.

Chạy cả frontend và backend bằng `docker compose up --build -d` từ thư mục gốc
project. Giao diện tại http://localhost:3000.

Hoặc chạy frontend trực tiếp:

```powershell
npm.cmd ci
npm.cmd run dev
```

Mở http://localhost:3000. Chế độ minh họa được bật sẵn; bấm
**Kết nối hệ thống thật** để dùng backend tại http://127.0.0.1:8000.

Hướng dẫn kết nối API, các màn hình và build production:
[docs/frontend.md](../docs/frontend.md).
