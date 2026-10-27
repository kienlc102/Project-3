import { Icon } from "../icons";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  "demo" | "currentCamera" | "slots" | "counts" | "occupancy"
>;
export function Metrics({
  demo,
  currentCamera,
  slots,
  counts,
  occupancy,
}: Props) {
  return (
    <div className="metrics">
      {[
        {
          label: "Tổng số ô đỗ",
          value: slots.length,
          note: "Trong cấu hình bãi xe",
          icon: "grid",
          color: "neutral",
        },
        {
          label: "Ô đang có xe",
          value: counts.occupied,
          note: `${occupancy}% tổng sức chứa`,
          icon: "car",
          color: "green",
        },
        {
          label: "Ô còn trống",
          value: counts.vacant,
          note: "Sẵn sàng đón xe",
          icon: "exit",
          color: "blue",
        },
        {
          label: "Chưa xác định",
          value: counts.unknown,
          note: "Cần kiểm tra trạng thái",
          icon: "signal",
          color: "amber",
        },
      ].map((m, i) => (
        <article className={`metric ${m.color}`} key={m.label}>
          <div className="metric-label">
            {m.label}
            <span className="metric-icon">
              <Icon name={m.icon} />
            </span>
          </div>
          <div className="metric-value">
            {!demo && !currentCamera ? "—" : String(m.value).padStart(2, "0")}
            <small>ô</small>
            {i === 1 && (
              <span className="mini-bars">
                {[12, 21, 17, 26, 22, 30, 26, 34].map((h, k) => (
                  <i key={k} style={{ height: h }} />
                ))}
              </span>
            )}
          </div>
          <p>
            <i className="dot" />
            {m.note}
          </p>
        </article>
      ))}
    </div>
  );
}
