import type { Camera, Frame, Status } from "./types";
import { Icon } from "../icons";

type Props = {
  demo: boolean;
  busy: boolean;
  camera: Camera | null;
  status: Status | null;
  target: string;
  setTarget: (value: string) => void;
  file: File | null;
  imageUrl: string;
  upload: () => void;
  run: () => void;
  frame: Frame | null;
};

export function ImageTestPanel({
  demo,
  busy,
  camera,
  status,
  target,
  setTarget,
  file,
  imageUrl,
  upload,
  run,
  frame,
}: Props) {
  return (
    <section className="panel image-test-panel">
      <div className="panel-heading">
        <div>
          <h2>Kiểm tra ảnh bãi xe</h2>
          <p>
            Chọn ảnh toàn cảnh cùng góc camera. Kết quả từng ô sẽ cập nhật lên
            mô hình xe bên dưới.
          </p>
        </div>
        <Icon name="upload" />
      </div>
      <div className="image-test-body">
        <div className="image-test-controls">
          <button
            className="button secondary"
            disabled={busy || demo}
            onClick={upload}
          >
            <Icon name="upload" size={16} /> Chọn ảnh từ máy tính
          </button>
          <span>
            {file?.name || "Chưa chọn ảnh · JPG, PNG, WebP, BMP · tối đa 10 MB"}
          </span>
          <label>
            Nơi chạy nhận diện
            <select
              value={target}
              disabled={busy || demo || !status}
              onChange={(e) => setTarget(e.target.value)}
            >
              {(status?.execution_targets || ["esp32"]).map((t) => (
                <option key={t} value={t}>
                  {t === "esp32"
                    ? "ESP32 · CNN INT8"
                    : t === "backend"
                      ? "Backend · CNN INT8"
                      : "YOLO"}
                </option>
              ))}
            </select>
          </label>
          <button
            className="button primary"
            disabled={busy || demo || !file || !camera || !status}
            onClick={run}
          >
            <Icon name={busy ? "refresh" : "arrow"} size={16} />
            {busy ? "Đang xử lý…" : "Nhận diện và cập nhật mô hình"}
          </button>
          <p>
            {camera
              ? `${camera.camera_id} · ${camera.slots.length} ô ROI · ảnh tham chiếu ${camera.reference_width} × ${camera.reference_height}`
              : "Chưa tải được cấu hình ROI. Kiểm tra kết nối backend."}
          </p>
          {demo && <p>Chuyển sang hệ thống thật để kiểm tra ảnh của bạn.</p>}
          {busy && (
            <p role="status">
              Đang chờ kết quả. Các ô được xử lý lần lượt trên thiết bị đã chọn.
            </p>
          )}
          {frame && !demo && (
            <p role="status">
              {frame.complete ? "Hoàn tất" : "Kết quả chưa đầy đủ"} ·{" "}
              {frame.counts.occupied} có xe · {frame.counts.vacant} trống ·{" "}
              {frame.counts.unknown} chưa xác định · {frame.execution_target}
            </p>
          )}
        </div>
        {imageUrl && (
          <div className="uploaded-frame">
            {/* Local object URL preserves original resolution for inspecting the uploaded frame. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageUrl}
              alt={file ? `Ảnh bãi xe: ${file.name}` : "Ảnh bãi xe"}
            />
          </div>
        )}
      </div>
    </section>
  );
}
