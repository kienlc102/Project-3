import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<DashboardState, "demo">;
export function DashboardFooter({ demo }: Props) {
  return (
    <footer className="footer">
      <span>
        <strong>parkly.</strong> Không gian đỗ xe, vận hành thông minh.
      </span>
      <span>
        {demo ? "CHẾ ĐỘ MINH HỌA" : "KẾT QUẢ CNN · CHƯA KẾT HỢP CẢM BIẾN"}{" "}
        <i>·</i> v1.0
      </span>
    </footer>
  );
}
