import { Car } from "../icons";
import type { Result } from "./types";
export function ParkingSlot({
  result,
  index,
  onClick,
}: {
  result: Result;
  index: number;
  onClick: () => void;
}) {
  const score =
    typeof result.car_score === "number" && Number.isFinite(result.car_score)
      ? result.car_score.toFixed(3)
      : null;
  const scoreLabel = score === null ? "Chưa có score" : `Score có xe: ${score}`;
  return (
    <button
      className={`parking-slot ${result.label === 1 ? "occupied" : result.label === 0 ? "vacant" : "unknown"}`}
      onClick={onClick}
      aria-label={`Ô ${result.slot_id}: ${result.label === 1 ? "có xe" : result.label === 0 ? "trống" : "chưa xác định"}. ${scoreLabel}`}
      title={`${result.slot_id} · ${scoreLabel}`}
    >
      <span className="slot-visual">
        {result.label === 1 ? (
          <Car
            color={["#587266", "#91a09a", "#667b88", "#b3b0a5"][index % 4]}
          />
        ) : (
          <span
            className={result.label === 0 ? "vacant-symbol" : "unknown-symbol"}
          >
            {result.label === 0 ? "P" : "?"}
          </span>
        )}
      </span>
      <span className="slot-id">{result.slot_id}</span>
      <span className="slot-score" aria-label={scoreLabel}>
        {score ?? "—"}
      </span>
    </button>
  );
}
