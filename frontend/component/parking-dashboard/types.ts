export type Slot = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
};
export type Camera = {
  camera_id: string;
  reference_width: number;
  reference_height: number;
  slots: Slot[];
  capture_device?: number | null;
  use_picamera2?: boolean;
};
export type Status = {
  ready: boolean;
  run: string;
  models: string[];
  threshold: number;
  execution_targets: string[];
  camera_configured: boolean;
  roi_count: number;
  default_target?: string;
  vision?: {
    model: string;
    confidence: number;
    overlap: number;
    image_size: number;
  };
};
export type Result = {
  slot_id: string;
  status: string;
  label: number | null;
  car_score?: number;
  latency_ms?: number;
  error?: string;
  threshold?: number;
  slot_coverage?: number;
  overlap_threshold?: number;
};
export type Frame = {
  camera_id: string;
  frame_id: string;
  execution_target: string;
  complete: boolean;
  results: Result[];
  counts: { occupied: number; vacant: number; unknown: number };
};
export type Entry = { id: string; time: string; source: string; frame: Frame };
export type View = "overview" | "slots" | "devices" | "history" | "settings";
