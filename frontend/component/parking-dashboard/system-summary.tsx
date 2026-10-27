import { Icon } from "../icons";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  "setView" | "demo" | "currentStatus" | "currentCamera"
>;
export function SystemSummary({
  setView,
  demo,
  currentStatus,
  currentCamera,
}: Props) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Trạng thái hệ thống</h2>
        <span className="badge">{demo ? "Minh họa" : "Gateway"}</span>
      </div>
      {[
        {
          icon: "camera",
          title: "Camera bãi đỗ",
          description: currentCamera?.camera_id || "Chưa có cấu hình",
          okay: !!currentCamera,
        },
        {
          icon: "signal",
          title: "Node suy luận ESP32",
          description: "Xác nhận kết nối qua suy luận",
          okay: !!currentStatus?.execution_targets.includes("esp32"),
        },
        {
          icon: "grid",
          title: "Mô hình nhận diện",
          description: currentStatus?.run || "Chưa kết nối",
          okay: !!currentStatus?.ready,
        },
      ].map((s) => (
        <div className="system-row" key={s.title}>
          <span className="system-icon">
            <Icon name={s.icon} />
          </span>
          <span>
            <strong>{s.title}</strong>
            <small>{s.description}</small>
          </span>
          <i className={`status-light ${s.okay ? "okay" : ""}`} />
        </div>
      ))}
      <button
        className="text-button system-link"
        onClick={() => setView("devices")}
      >
        Quản lý thiết bị
        <Icon name="arrow" size={15} />
      </button>
    </section>
  );
}
