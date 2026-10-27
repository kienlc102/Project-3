import type { Entry } from "./types";
export function ActivityChart({
  demo,
  entries,
}: {
  demo: boolean;
  entries: Entry[];
}) {
  const bars = demo
    ? [
        3, 5, 4, 8, 12, 16, 13, 18, 22, 17, 14, 19, 15, 12, 16, 21, 18, 14, 10,
        8, 6, 4, 3, 2,
      ]
    : Array.from(
        { length: 24 },
        (_, h) =>
          entries.filter(
            (e) =>
              Number(
                new Date(e.time).toLocaleString("en-US", {
                  hour: "2-digit",
                  hourCycle: "h23",
                  timeZone: "Asia/Ho_Chi_Minh",
                }),
              ) === h,
          ).length,
      );
  const max = Math.max(...bars, 1);
  return (
    <div className="chart-wrap">
      <div className="chart-scale">
        <span>{max}</span>
        <span>{Math.round(max / 2)}</span>
        <span>0</span>
      </div>
      <div className="chart">
        <div
          className="chart-bars"
          role="img"
          aria-label={
            demo
              ? "Lượt kiểm tra minh họa theo giờ"
              : "Số lượt kiểm tra theo giờ trong phiên"
          }
        >
          {bars.map((v, i) => (
            <div
              key={i}
              className={`chart-bar ${i === 8 ? "highlight" : ""}`}
              style={{ height: `${(v / max) * 100}%`, minHeight: v ? 4 : 0 }}
              title={`${i}:00 — ${v} lượt kiểm tra`}
            />
          ))}
        </div>
        <div className="chart-hours">
          {["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "23:00"].map(
            (h) => (
              <span key={h}>{h}</span>
            ),
          )}
        </div>
      </div>
    </div>
  );
}
