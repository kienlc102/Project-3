import { Icon } from "../icons";
import { nav } from "./data";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<DashboardState, "view" | "demo" | "lotName" | "switchMode">;
export function PageHeading({ view, demo, lotName, switchMode }: Props) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">PARKLY / TRUNG TÂM ĐIỀU HÀNH</div>
        <h1>
          {view === "overview"
            ? "Một góc nhìn. Toàn bộ bãi xe."
            : nav.find((n) => n.id === view)?.name}
        </h1>
        <p>
          {view === "overview"
            ? "Nắm bắt tình trạng bãi đỗ và chủ động trong từng quyết định."
            : `Quản lý và theo dõi ${lotName.toLowerCase()}.`}
        </p>
      </div>
      <button className="button secondary" onClick={switchMode}>
        <i className={`dot ${demo ? "amber" : ""}`} />
        {demo ? "Kết nối hệ thống thật" : "Xem bản minh họa"}
        <Icon name="arrow" size={16} />
      </button>
    </div>
  );
}
