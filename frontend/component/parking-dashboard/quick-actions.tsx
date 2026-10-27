import { Icon } from "../icons";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  "demo" | "status" | "busy" | "scan" | "upload"
>;
export function QuickActions({ demo, status, busy, scan, upload }: Props) {
  return (
    <section className="quick-card">
      <Icon name="camera" size={24} />
      <h2>Kiểm tra bãi xe</h2>
      <p>Lấy ảnh mới từ camera để cập nhật trạng thái các ô đỗ.</p>
      <button
        className="button primary"
        disabled={busy || (!demo && !status)}
        onClick={() => void scan()}
      >
        <Icon name={busy ? "refresh" : "camera"} size={17} />
        {busy ? "Đang xử lý…" : "Kiểm tra từ camera"}
        <Icon name="arrow" size={16} />
      </button>
      <button className="upload-link" disabled={busy} onClick={upload}>
        <Icon name="upload" size={14} />
        Hoặc tải ảnh bãi xe lên
      </button>
    </section>
  );
}
