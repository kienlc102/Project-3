import { useEffect, useRef } from "react";
import { Car, Icon } from "../icons";
import { StatusBadge } from "./status-badge";
import type { Result } from "./types";
export function SlotDialog({
  result,
  demo,
  target,
  threshold,
  onClose,
}: {
  result: Result;
  demo: boolean;
  target?: string;
  threshold?: number;
  onClose: () => void;
}) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    close.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        event.preventDefault();
        close.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="slot-dialog-title"
        className="detail-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="panel-heading">
          <h2 id="slot-dialog-title">Ô đỗ {result.slot_id}</h2>
          <button
            ref={close}
            className="icon-button"
            aria-label="Đóng chi tiết"
            onClick={onClose}
          >
            <Icon name="close" />
          </button>
        </div>
        <div className="detail-content">
          <StatusBadge result={result} />
          <div className="detail-car">
            <Car color={result.label === 1 ? "#4a6d60" : "#a6b6b0"} />
          </div>
          <dl>
            {[
              ["Nguồn dữ liệu", demo ? "Minh họa" : target || "Chưa kiểm tra"],
              [
                target === "raspberry_pi"
                  ? "Độ tin cậy phát hiện xe"
                  : "Điểm nhận diện xe",
                result.car_score !== undefined
                  ? `${(result.car_score * 100).toFixed(1)}%`
                  : "—",
              ],
              [
                target === "raspberry_pi"
                  ? "Thời gian xử lý toàn ảnh"
                  : "Thời gian suy luận",
                result.latency_ms !== undefined
                  ? `${result.latency_ms} ms`
                  : "—",
              ],
              [
                target === "raspberry_pi"
                  ? "Ngưỡng phát hiện"
                  : "Ngưỡng phân loại",
                result.threshold ?? threshold ?? "—",
              ],
              ...(target === "raspberry_pi"
                ? [
                    [
                      "Phần ô được xe che phủ",
                      `${((result.slot_coverage ?? 0) * 100).toFixed(1)}%`,
                    ],
                    [
                      "Ngưỡng che phủ",
                      `${((result.overlap_threshold ?? 0) * 100).toFixed(1)}%`,
                    ],
                  ]
                : []),
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          {result.error && <p className="detail-error">{result.error}</p>}
          <p className="muted">
            Kết quả từ ảnh phản ánh thời điểm kiểm tra, không phải trạng thái
            được xác nhận liên tục.
            {target === "raspberry_pi" &&
              " Điểm 0 chỉ có nghĩa chưa phát hiện xe, không phải độ chắc chắn ô trống."}
          </p>
        </div>
      </section>
    </div>
  );
}
