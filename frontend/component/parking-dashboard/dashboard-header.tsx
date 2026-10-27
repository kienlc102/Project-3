import { Icon } from "../icons";
import { nav } from "./data";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  "view" | "setView" | "demo" | "status" | "setNotice" | "counts"
>;
export function DashboardHeader({
  view,
  setView,
  demo,
  status,
  setNotice,
  counts,
}: Props) {
  return (
    <header className="topbar">
      <div className="breadcrumb">
        Không gian quản lý <Icon name="chevron" size={12} />
        <strong>{nav.find((n) => n.id === view)?.name}</strong>
      </div>
      <div className="topbar-right">
        <span
          className={`connection ${demo ? "demo" : status ? "online" : "offline"}`}
        >
          <i />
          {demo
            ? "Dữ liệu minh họa"
            : status
              ? "Đã kết nối gateway"
              : "Chưa kết nối"}
        </span>
        <button
          className="icon-button"
          aria-label="Xem cảnh báo hệ thống"
          onClick={() => {
            setView("devices");
            setNotice(
              counts.unknown
                ? `Có ${counts.unknown} ô chưa xác định. Kiểm tra kết nối và kết quả suy luận.`
                : "Không có cảnh báo trong kết quả hiện tại.",
            );
          }}
        >
          <Icon name="bell" />
          <i className="notification-dot" />
        </button>
        <span className="avatar small">QL</span>
      </div>
    </header>
  );
}
