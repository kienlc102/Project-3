import { Icon } from "../icons";
import { ActivityChart } from "./activity-chart";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<DashboardState, "setView" | "demo" | "entries">;
export function ActivityPanel({ setView, demo, entries }: Props) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Hoạt động kiểm tra</h2>
          <p>
            {demo
              ? "Minh họa số lượt kiểm tra trong ngày"
              : "Các lần kiểm tra trong phiên làm việc này"}
          </p>
        </div>
        <button className="text-button" onClick={() => setView("history")}>
          Xem tất cả
          <Icon name="arrow" size={15} />
        </button>
      </div>
      <ActivityChart entries={entries} demo={demo} />
    </section>
  );
}
