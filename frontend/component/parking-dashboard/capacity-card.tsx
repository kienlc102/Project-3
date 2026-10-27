import { Icon } from "../icons";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  "demo" | "currentFrame" | "counts" | "occupancy"
>;
export function CapacityCard({ demo, currentFrame, counts, occupancy }: Props) {
  return (
    <section className="panel capacity">
      <div className="panel-heading">
        <h2>Mức sử dụng</h2>
        <Icon name="car" size={18} />
      </div>
      <div
        className="capacity-ring"
        style={{
          background: `conic-gradient(#28664f ${occupancy}%, #edf0e9 0)`,
        }}
      >
        <div>
          <strong>
            {occupancy}
            <small>%</small>
          </strong>
          <span>Đang có xe</span>
        </div>
      </div>
      <p className="capacity-note">
        <i className="dot" />{" "}
        {demo || currentFrame
          ? counts.vacant
            ? "Bãi xe vẫn còn chỗ trống"
            : "Kiểm tra kết quả từng ô"
          : "Chưa có kết quả kiểm tra"}
      </p>
      <div className="capacity-split">
        <span>
          <i className="dot" />
          Có xe<strong>{counts.occupied}</strong>
        </span>
        <span>
          <i className="dot blue" />
          Còn trống<strong>{counts.vacant}</strong>
        </span>
      </div>
    </section>
  );
}
