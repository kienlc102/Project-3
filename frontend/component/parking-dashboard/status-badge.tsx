import type { Result } from "./types";
export function StatusBadge({ result }: { result: Result }) {
  return (
    <span
      className={`state-badge ${result.label === 1 ? "occupied" : result.label === 0 ? "vacant" : "unknown"}`}
    >
      <i />
      {result.label === 1
        ? "Có xe"
        : result.label === 0
          ? "Còn trống"
          : "Chưa xác định"}
    </span>
  );
}
