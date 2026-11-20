import { Icon } from "../icons";
import { displayTime } from "./format";
import { ParkingSlot } from "./parking-slot";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  | "layout"
  | "setLayout"
  | "columns"
  | "setColumns"
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
  layout,
  setLayout,
  columns,
  setColumns,
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
      <div className="layout-controls">
        <label>
          Bố cục mô phỏng
          <select
            value={layout}
            onChange={(e) => setLayout(e.target.value as "roi" | "grid")}
          >
            <option value="roi">Theo tọa độ ROI</option>
            <option value="grid">Lưới ô đỗ</option>
          </select>
        </label>
        {layout === "grid" && (
          <label>
            Số cột
            <input
              type="number"
              min={2}
              max={12}
              value={columns}
              onChange={(e) =>
                setColumns(
                  Math.max(2, Math.min(12, Number(e.target.value) || 2)),
                )
              }
            />
          </label>
        )}
        <span>
          {currentCamera
            ? `${currentCamera.camera_id} · ${currentCamera.reference_width} × ${currentCamera.reference_height}`
            : "Đang chờ ROI backend"}
        </span>
      </div>
      <div className="parking-map roi-map-scroll">
        {slots.length && currentCamera ? (
          <div
            className={layout === "roi" ? "roi-simulation" : "simulation-grid"}
            style={
              layout === "roi"
                ? {
                    aspectRatio: `${currentCamera.reference_width} / ${currentCamera.reference_height}`,
                  }
                : {
                    gridTemplateColumns: `repeat(${columns}, minmax(55px, 1fr))`,
                  }
            }
          >
            {slots.map((slot, index) => {
              const result = results.find((r) => r.slot_id === slot.id)!;
              return (
                <div
                  key={slot.id}
                  className={
                    layout === "roi" ? "roi-position" : "grid-position"
                  }
                  style={
                    layout === "roi"
                      ? {
                          left: `${(slot.x / currentCamera.reference_width) * 100}%`,
                          top: `${(slot.y / currentCamera.reference_height) * 100}%`,
                          width: `${(slot.width / currentCamera.reference_width) * 100}%`,
                          height: `${(slot.height / currentCamera.reference_height) * 100}%`,
                        }
                      : undefined
                  }
                >
                  <ParkingSlot
                    result={result}
                    index={index}
                    onClick={() => setSelected(result)}
                  />
                </div>
              );
            })}
          </div>
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
            {demo ? "Sơ đồ minh họa" : "Đồng bộ ô đỗ từ ROI backend"}
          </span>
          <span>
            {layout === "roi"
              ? "Vị trí theo ảnh tham chiếu"
              : "Bố cục lưới tùy chỉnh"}
          </span>
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
