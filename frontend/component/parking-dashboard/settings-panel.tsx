import { Icon } from "../icons";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  | "demo"
  | "status"
  | "setNotice"
  | "lotName"
  | "setLotName"
  | "auto"
  | "setAuto"
>;
export function SettingsPanel({
  demo,
  status,
  setNotice,
  lotName,
  setLotName,
  auto,
  setAuto,
}: Props) {
  return (
    <section className="panel settings-panel">
      <div className="panel-heading">
        <div>
          <h2>Tùy chỉnh không gian</h2>
          <p>Cài đặt hiển thị cho trình duyệt này.</p>
        </div>
        <Icon name="settings" />
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const name = lotName.trim();
          if (!name) return;
          setLotName(name);
          localStorage.setItem("parkly-lot-name", name);
          setNotice("Đã lưu tên hiển thị trên trình duyệt này.");
        }}
      >
        <label>
          Tên bãi đỗ xe
          <input
            value={lotName}
            maxLength={70}
            required
            onChange={(e) => setLotName(e.target.value)}
          />
        </label>
        <div className="setting-toggle">
          <span>
            <strong>Tự kiểm tra camera mỗi 30 giây</strong>
            <small>
              Chỉ hoạt động trong chế độ hệ thống thật, khi trang đang hiển thị.
            </small>
          </span>
          <input
            type="checkbox"
            aria-label="Tự kiểm tra camera"
            checked={auto}
            disabled={demo || !status}
            onChange={(e) => setAuto(e.target.checked)}
          />
        </div>
        <button className="button primary" type="submit">
          <Icon name="check" size={17} />
          Lưu thay đổi
        </button>
      </form>
      <div className="info-note">
        <Icon name="info" />
        <p>
          Cấu hình ROI, địa chỉ camera và ESP32 hiện được quản lý trên backend.
          Giao diện chưa có API chỉnh sửa cấu hình hoặc xác thực tài khoản.
        </p>
      </div>
    </section>
  );
}
