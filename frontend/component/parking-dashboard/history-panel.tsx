import { Icon } from "../icons";
import { displayTime } from "./format";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<DashboardState, "setView" | "demo" | "entries">;
export function HistoryPanel({ setView, demo, entries }: Props) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Nhật ký kiểm tra trong phiên</h2>
          <p>
            Lịch sử được giữ trong bộ nhớ đến khi tải lại trang hoặc đổi chế độ.
          </p>
        </div>
        <span className="badge">{entries.length} lần kiểm tra</span>
      </div>
      {!entries.length ? (
        <div className="empty-state">
          <Icon name="clock" size={38} />
          <h3>Chưa có lượt kiểm tra</h3>
          <p>
            {demo
              ? "Chuyển sang hệ thống thật và kiểm tra camera để bắt đầu ghi nhận."
              : "Kiểm tra camera hoặc tải ảnh để lưu kết quả trong phiên này."}
          </p>
          <button
            className="button secondary"
            onClick={() => setView("devices")}
          >
            Đến camera & thiết bị
            <Icon name="arrow" size={16} />
          </button>
        </div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>THỜI ĐIỂM</th>
                <th>NGUỒN</th>
                <th>CÓ XE / TRỐNG / CHƯA RÕ</th>
                <th>KẾT QUẢ</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td>{displayTime(e.time)}</td>
                  <td>{e.source}</td>
                  <td>
                    {e.frame.counts.occupied} / {e.frame.counts.vacant} /{" "}
                    {e.frame.counts.unknown}
                  </td>
                  <td>
                    <span
                      className={`state-badge ${e.frame.complete ? "vacant" : "unknown"}`}
                    >
                      {e.frame.complete ? "Hoàn tất" : "Có ô chưa xác định"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
