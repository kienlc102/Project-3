import { Icon } from "../icons";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  | "demo"
  | "status"
  | "setFrame"
  | "busy"
  | "setNotice"
  | "target"
  | "setTarget"
  | "currentStatus"
  | "currentCamera"
  | "slots"
  | "refresh"
  | "scan"
  | "upload"
>;
export function DevicesPanel({
  demo,
  status,
  setFrame,
  busy,
  setNotice,
  target,
  setTarget,
  currentStatus,
  currentCamera,
  slots,
  refresh,
  scan,
  upload,
}: Props) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Kết nối & nguồn dữ liệu</h2>
          <p>Trạng thái cấu hình không thay thế kiểm tra kết nối thiết bị.</p>
        </div>
        <button
          className="button secondary"
          disabled={busy}
          onClick={() =>
            demo
              ? setNotice(
                  "Chuyển sang hệ thống thật để đọc trạng thái gateway.",
                )
              : void refresh()
          }
        >
          <Icon name="refresh" size={16} />
          Làm mới
        </button>
      </div>
      <div className="device-grid">
        {[
          {
            icon: "grid",
            name: "Gateway suy luận",
            state: currentStatus?.ready ? "Sẵn sàng" : "Chưa kết nối",
            detail: `Model: ${currentStatus?.run || "—"}`,
            sub: `Định dạng: ${currentStatus?.models.join(", ") || "—"}`,
          },
          {
            icon: "camera",
            name: "Camera cố định",
            state: currentCamera ? "Đã cấu hình ROI" : "Chưa cấu hình",
            detail: currentCamera?.camera_id || "Cấu hình camera trên backend",
            sub: `${slots.length} vùng nhận diện · ${currentCamera?.use_picamera2 ? "Camera CSI" : currentCamera?.capture_device != null ? "Camera USB" : "HTTP snapshot"}`,
          },
          {
            icon: "grid",
            name: "Raspberry Pi · camera",
            state: currentStatus?.execution_targets.includes("raspberry_pi")
              ? "Đã bật"
              : "Chưa cấu hình",
            detail:
              currentStatus?.vision?.model ||
              "Nhận diện xe bằng YOLO pretrained",
            sub: "Chỉ dùng camera · Không cần cảm biến khoảng cách",
          },
          {
            icon: "signal",
            name: "Node ESP32",
            state: currentStatus?.execution_targets.includes("esp32")
              ? "Đã cấu hình"
              : "Chưa cấu hình",
            detail: "Kết nối được xác nhận khi suy luận thành công",
            sub: "Grayscale 64 × 64 · INT8",
          },
        ].map((d) => (
          <article className="device" key={d.name}>
            <span className="device-icon">
              <Icon name={d.icon} size={28} />
            </span>
            <h3>{d.name}</h3>
            <span className="badge">{d.state}</span>
            <p>{d.detail}</p>
            <small>{d.sub}</small>
          </article>
        ))}
      </div>
      <div className="device-actions">
        <label>
          Nơi thực thi
          <select
            value={target}
            onChange={(e) => {
              setTarget(e.target.value);
              setFrame(null);
            }}
            disabled={demo || !status || busy}
          >
            {(currentStatus?.execution_targets || ["esp32"]).map((t) => (
              <option key={t} value={t}>
                {t === "esp32"
                  ? "ESP32 · INT8"
                  : t === "raspberry_pi"
                    ? "Raspberry Pi · Camera + YOLO"
                    : "Backend · tham chiếu"}
              </option>
            ))}
          </select>
        </label>
        <button
          className="button primary"
          onClick={() => void scan()}
          disabled={busy || (!demo && !status)}
        >
          <Icon name="camera" size={17} />
          Kiểm tra camera
        </button>
        <button className="button secondary" disabled={busy} onClick={upload}>
          <Icon name="upload" size={17} />
          Tải ảnh kiểm tra
        </button>
      </div>
      <div className="info-note">
        <Icon name="info" />
        <p>
          {target === "raspberry_pi"
            ? "YOLO nhận diện xe trên toàn ảnh và đối chiếu với vùng từng ô. Xe sát ranh giới có thể được đánh dấu chưa xác định. Cần hiệu chỉnh ROI theo camera thực tế."
            : "Kết quả hiện tại là nhận diện CNN từ ảnh. Backend chưa cung cấp dữ liệu cảm biến khoảng cách và kết quả kết hợp cảm biến."}
        </p>
      </div>
    </section>
  );
}
