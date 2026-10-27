import { Icon } from "../icons";
import { displayTime } from "./format";
import { ParkingSlot } from "./parking-slot";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  | "view"
  | "setView"
  | "demo"
  | "busy"
  | "setNotice"
  | "updated"
  | "setSelected"
  | "lotName"
  | "currentCamera"
  | "slots"
  | "results"
  | "refresh"
>;
export function ParkingMap({
  view,
  setView,
  demo,
  busy,
  setNotice,
  updated,
  setSelected,
  lotName,
  currentCamera,
  slots,
  results,
  refresh,
}: Props) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>
            Sơ đồ bãi đỗ <span className="badge">{slots.length} ô</span>
          </h2>
          <p>
            {lotName} <span className="separator">/</span>{" "}
            {demo
              ? "Khu A & Khu B"
              : currentCamera?.camera_id || "Chưa cấu hình camera"}
          </p>
        </div>
        <button
          className={`icon-button ${busy ? "spinning" : ""}`}
          aria-label="Làm mới trạng thái hệ thống"
          disabled={busy}
          onClick={() =>
            demo
              ? setNotice(
                  "Bản minh họa dùng dữ liệu cố định. Kết nối hệ thống thật để cập nhật.",
                )
              : void refresh()
          }
        >
          <Icon name="refresh" size={18} />
        </button>
      </div>
      <div className="map-toolbar">
        <div className="legend">
          <span>
            <i />
            Có xe
          </span>
          <span>
            <i className="vacant" />
            Trống
          </span>
          <span>
            <i className="unknown" />
            Chưa xác định
          </span>
        </div>
        <span>Chọn ô để xem chi tiết</span>
      </div>
      <div className="parking-map">
        <div className="north">N ↑</div>
        <div className="landscape">
          <i />
          <i />
          <i />
          <span>LỐI ĐI BỘ</span>
          <i />
          <i />
          <i />
        </div>
        {slots.length ? (
          <>
            <div className="parking-row">
              {results.slice(0, Math.ceil(results.length / 2)).map((r, i) => (
                <ParkingSlot
                  key={r.slot_id}
                  result={r}
                  index={i}
                  onClick={() => setSelected(r)}
                />
              ))}
            </div>
            <div className="driving-lane">
              <span>↑ VÀO</span>
              <i />
              <b>→</b>
              <span>LỐI DI CHUYỂN</span>
              <b>→</b>
              <i />
              <span>RA ↓</span>
            </div>
            <div className="parking-row lower">
              {results.slice(Math.ceil(results.length / 2)).map((r, i) => (
                <ParkingSlot
                  key={r.slot_id}
                  result={r}
                  index={i + 12}
                  onClick={() => setSelected(r)}
                />
              ))}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <Icon name="car" size={36} />
            <h3>Chưa có sơ đồ ô đỗ</h3>
            <p>Kết nối backend và cấu hình ROI để hiển thị các ô đỗ.</p>
            <button
              className="button secondary"
              onClick={() => setView("devices")}
            >
              Xem trạng thái hệ thống
            </button>
          </div>
        )}
        <div className="map-bottom">
          <span>
            <i className="dot" />{" "}
            {demo ? "Sơ đồ minh họa" : "Bố cục tổng hợp từ danh sách ROI"}
          </span>
          <span>Không theo tỷ lệ thực tế</span>
        </div>
      </div>
      <div className="panel-footer">
        <span>
          <Icon name="clock" size={13} />
          {demo
            ? "Bản xem trước · dữ liệu cố định"
            : updated
              ? `Cập nhật lúc ${displayTime(updated)}`
              : "Đang chờ dữ liệu"}
        </span>
        <button
          className="text-button"
          onClick={() => setView(view === "overview" ? "slots" : "history")}
        >
          {view === "overview" ? "Xem danh sách ô đỗ" : "Xem lịch sử kiểm tra"}
          <Icon name="arrow" size={15} />
        </button>
      </div>
    </section>
  );
}
