import type { View, Slot, Camera, Frame, Status } from "./types";
export const nav: { id: View; name: string; icon: string }[] = [
  { id: "overview", name: "Tổng quan", icon: "grid" },
  { id: "slots", name: "Quản lý ô đỗ", icon: "car" },
  { id: "devices", name: "Camera & thiết bị", icon: "camera" },
  { id: "history", name: "Lịch sử kiểm tra", icon: "clock" },
  { id: "settings", name: "Cài đặt", icon: "settings" },
];
export const demoSlots: Slot[] = Array.from({ length: 24 }, (_, i) => ({
  id: `${i < 12 ? "A" : "B"}-${String((i % 12) + 1).padStart(2, "0")}`,
  x: (i % 12) * 100,
  y: i < 12 ? 0 : 200,
  width: 90,
  height: 180,
}));
export const demoCamera: Camera = {
  camera_id: "camera_demo",
  reference_width: 1200,
  reference_height: 400,
  slots: demoSlots,
};
export const demoFrame: Frame = {
  camera_id: "camera_demo",
  frame_id: "demo",
  execution_target: "esp32",
  complete: false,
  counts: { occupied: 16, vacant: 7, unknown: 1 },
  results: demoSlots.map((s, i) => ({
    slot_id: s.id,
    status: i === 20 ? "unknown" : "ok",
    label: i === 20 ? null : [2, 5, 8, 10, 14, 17, 22].includes(i) ? 0 : 1,
    car_score:
      i === 20
        ? undefined
        : [2, 5, 8, 10, 14, 17, 22].includes(i)
          ? 0.08
          : 0.96,
    latency_ms: i === 20 ? undefined : 3.2,
  })),
};
export const demoStatus: Status = {
  ready: true,
  run: "run_gpu01",
  models: ["int8"],
  threshold: 0.75,
  execution_targets: ["esp32"],
  camera_configured: true,
  roi_count: 24,
};
