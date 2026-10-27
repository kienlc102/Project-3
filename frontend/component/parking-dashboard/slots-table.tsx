import { Icon } from "../icons";
import { StatusBadge } from "./status-badge";
import type { DashboardState } from "./use-parking-dashboard";
type Props = Pick<
  DashboardState,
  | "query"
  | "setQuery"
  | "filter"
  | "setFilter"
  | "setSelected"
  | "slots"
  | "visible"
  | "exportCsv"
>;
export function SlotsTable({
  query,
  setQuery,
  filter,
  setFilter,
  setSelected,
  slots,
  visible,
  exportCsv,
}: Props) {
  return (
    <section className="panel table-panel">
      <div className="panel-heading">
        <h2>Danh sách ô đỗ</h2>
        <button
          className="button secondary"
          onClick={exportCsv}
          disabled={!slots.length}
        >
          <Icon name="download" size={16} />
          Xuất CSV
        </button>
      </div>
      <div className="table-controls">
        <label className="search">
          <Icon name="search" size={17} />
          <input
            aria-label="Tìm ô đỗ"
            placeholder="Tìm theo mã ô đỗ…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <select
          aria-label="Lọc trạng thái ô đỗ"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">Tất cả trạng thái</option>
          <option value="occupied">Có xe</option>
          <option value="vacant">Còn trống</option>
          <option value="unknown">Chưa xác định</option>
        </select>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>MÃ Ô ĐỖ</th>
              <th>TRẠNG THÁI</th>
              <th>ĐIỂM NHẬN DIỆN XE</th>
              <th>THỜI GIAN SUY LUẬN</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.slot_id}>
                <td>
                  <strong>{r.slot_id}</strong>
                </td>
                <td>
                  <StatusBadge result={r} />
                </td>
                <td>
                  {r.car_score !== undefined
                    ? `${(r.car_score * 100).toFixed(1)}%`
                    : "—"}
                </td>
                <td>
                  {r.latency_ms !== undefined ? `${r.latency_ms} ms` : "—"}
                </td>
                <td>
                  <button
                    className="text-button"
                    onClick={() => setSelected(r)}
                  >
                    Chi tiết
                    <Icon name="chevron" size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!visible.length && (
          <div className="empty-state">Không có ô đỗ phù hợp.</div>
        )}
      </div>
    </section>
  );
}
