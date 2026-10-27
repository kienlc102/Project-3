import { Icon } from "../icons";
import { nav } from "./data";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  "view" | "setView" | "setQuery" | "lotName" | "slots"
>;
export function Sidebar({ view, setView, setQuery, lotName, slots }: Props) {
  return (
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Parkly trang chủ">
        <span className="brand-symbol">
          P<i />
        </span>
        parkly<span className="brand-dot">.</span>
      </a>
      <span className="workspace-label">KHÔNG GIAN QUẢN LÝ</span>
      <button className="lot-switch" onClick={() => setView("settings")}>
        <span className="lot-mark">
          <Icon name="car" />
        </span>
        <span>
          <strong>{lotName}</strong>
          <small>Không gian chủ bãi</small>
        </span>
        <Icon name="chevron" size={14} />
      </button>
      <div className="nav-label">VẬN HÀNH</div>
      <nav aria-label="Điều hướng chính">
        {nav.map((n) => (
          <button
            key={n.id}
            className={`nav-item ${view === n.id ? "active" : ""}`}
            title={n.name}
            onClick={() => {
              setView(n.id);
              setQuery("");
            }}
            aria-current={view === n.id ? "page" : undefined}
          >
            <Icon name={n.icon} />
            <span>{n.name}</span>
            {n.id === "slots" && (
              <b className="nav-count">{slots.length || "—"}</b>
            )}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="help-card">
          <Icon name="signal" />
          <strong>Mỗi ô đỗ, một góc nhìn.</strong>
          <p>Theo dõi bãi xe trong một không gian duy nhất.</p>
          <button onClick={() => setView("devices")}>
            Kiểm tra hệ thống <Icon name="arrow" size={15} />
          </button>
        </div>
        <div className="profile">
          <span className="avatar">QL</span>
          <span>
            <strong>Chủ bãi đỗ xe</strong>
            <small>Quản lý hệ thống</small>
          </span>
          <Icon name="settings" size={17} />
        </div>
      </div>
    </aside>
  );
}
