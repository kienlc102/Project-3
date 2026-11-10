"""Optional full-frame YOLO detector; no TensorFlow or ESP32 dependency."""
import logging
import math
import threading
import time
import uuid

from backend.config.settings import MAX_UPLOAD_BYTES
from backend.config.vision import (DEFAULT_VISION_EDGE_MARGIN, DEFAULT_VISION_ROTATIONS,
                                   PARKING_CAR_FILENAME, PARKING_CAR_PROFILE, PARKING_CAR_SOURCE,
                                   resolve_vision_model)
from backend.model.vision_fusion import fuse_detections, restore_box, select_cars

# Camera branch counts passenger cars only. Model label IDs vary across weights.
VEHICLE_CLASSES = ("car",)


class VisionPredictor:
    def __init__(self, model_path, confidence=0.75, overlap=0.25, image_size=640,
                 rotations=DEFAULT_VISION_ROTATIONS, edge_margin=DEFAULT_VISION_EDGE_MARGIN):
        path = resolve_vision_model(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Vision model not found: {path}. Run python -m ai_model.prepare_vision_model first.")
        if not math.isfinite(confidence) or not 0 < confidence <= 1:
            raise ValueError("Vision confidence must be in (0, 1]")
        if not math.isfinite(overlap) or not 0 < overlap <= 1:
            raise ValueError("Vision overlap must be in (0, 1]")
        if image_size < 32 or image_size % 32:
            raise ValueError("Vision image size must be a positive multiple of 32")
        rotations = tuple(rotations)
        if (not rotations or len(set(rotations)) != len(rotations)
                or any(angle not in (0, 90, 180, 270) for angle in rotations)):
            raise ValueError("Vision rotations must be unique quarter turns: 0, 90, 180, 270")
        if not math.isfinite(edge_margin) or edge_margin < 0:
            raise ValueError("Vision edge margin must be finite and nonnegative")
        from ultralytics import YOLO
        self.model = YOLO(str(path), task="detect")
        self.model_path = path
        self.confidence, self.overlap, self.image_size = confidence, overlap, image_size
        self.rotations, self.edge_margin = rotations, edge_margin
        self.min_support_views = min(2, len(rotations))
        self.lock = threading.Lock()

    @property
    def candidate_confidence(self):
        return min(self.confidence, 0.35) if len(self.rotations) > 1 else self.confidence

    def status(self):
        return {"ready": True, "run": self.model_path.name, "models": ["yolo"],
                "threshold": self.confidence, "threshold_source": "configured",
                "max_upload_bytes": MAX_UPLOAD_BYTES, "execution_targets": ["raspberry_pi"],
                "vision": {"model": self.model_path.name, "confidence": self.confidence,
                           "overlap": self.overlap, "image_size": self.image_size,
                           "device": "cpu", "vehicle_classes": list(VEHICLE_CLASSES),
                           "rotations": list(self.rotations), "min_support_views": self.min_support_views,
                           "candidate_confidence": self.candidate_confidence,
                           "image_count_edge_margin_px": self.edge_margin,
                           "profile": PARKING_CAR_PROFILE if self.model_path.name == PARKING_CAR_FILENAME else "custom",
                           "source": PARKING_CAR_SOURCE if self.model_path.name == PARKING_CAR_FILENAME else None}}

    def _infer(self, image):
        # PIL RGB input keeps Ultralytics' channel handling consistent for every source.
        image = image.convert("RGB")
        views = []
        with self.lock:
            for angle in self.rotations:
                source = image.rotate(angle, expand=True) if angle else image
                output = self.model.predict(source=source, imgsz=self.image_size,
                                            conf=self.candidate_confidence, device="cpu", verbose=False)[0]
                boxes = output.boxes
                if boxes is None:
                    raise RuntimeError("Model did not return detection boxes")
                # Resolve by names rather than hardcoded COCO IDs, supporting custom weights too.
                if not {name.strip().casefold() for name in output.names.values()} & set(VEHICLE_CLASSES):
                    raise RuntimeError("Model has no supported car class")
                for box, score, class_id in zip(boxes.xyxy.cpu().tolist(), boxes.conf.cpu().tolist(),
                                                boxes.cls.cpu().tolist()):
                    name = output.names[int(class_id)].strip().casefold()
                    if (len(box) != 4 or not all(math.isfinite(v) for v in [*box, score]) or not 0 < score <= 1
                            or box[2] <= box[0] or box[3] <= box[1]):
                        raise RuntimeError("Detector returned invalid vehicle coordinates or confidence")
                    restored = restore_box(box, angle, *image.size)
                    if restored[2] <= restored[0] or restored[3] <= restored[1]:
                        raise RuntimeError("Detector returned a box outside the image")
                    views.append({"box": restored, "confidence": score, "class_name": name, "rotation": angle})
        if len(self.rotations) == 1:
            return [{k: v for k, v in d.items() if k != "rotation"} for d in views], views
        return fuse_detections(views, self.min_support_views), views

    def _detect_all_classes(self, image):
        return self._infer(image)[0]

    def detect(self, image):
        # ROI occupancy can use a partially visible car; full-image counting has its own border policy.
        return select_cars(self._detect_all_classes(image), self.confidence, image.size)[0]

    def predict_image(self, image, debug=False):
        started = time.perf_counter()
        raw, views = self._infer(image)
        detections, rejected = select_cars(raw, self.confidence, image.size, self.edge_margin)
        result = {"request_id": uuid.uuid4().hex, "execution_target": "raspberry_pi",
                "model": "yolo", "run": self.model_path.name, "original_size": list(image.size),
                "confidence_threshold": self.confidence, "detected": bool(detections),
                "vehicle_count": len(detections), "detections": detections,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "latency_scope": "full_frame"}
        if debug:
            result["diagnostics"] = {
                "reason": ("vehicles_detected" if detections else "vehicles_filtered" if rejected
                           else "only_non_vehicle_detections" if raw else "no_detections"),
                "vehicle_classes": list(VEHICLE_CLASSES), "raw_detections": raw,
                "view_detections": views, "rejected_detections": rejected,
                "rotations": list(self.rotations), "min_support_views": self.min_support_views,
                "candidate_confidence": self.candidate_confidence, "edge_margin_px": self.edge_margin}
        return result

    def predict_frame(self, image, camera):
        # Validate geometry before running an expensive model, including aspect ratio checks.
        slots = list(camera.boxes(image))
        frame_id = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            detections = self.detect(image)
        except Exception:
            logging.getLogger("uvicorn.error").exception("Vision inference failed")
            return self._frame(image, camera, frame_id, [
                {"slot_id": slot_id, "box": box, "status": "unknown", "label": None,
                 "execution_target": "raspberry_pi", "error": "Không thể chạy model camera. Xem terminal backend."}
                for slot_id, box in slots], [], started)
        results = []
        for slot_id, box in slots:
            slot_area = (box[2] - box[0]) * (box[3] - box[1])
            matches = []
            for detection in detections:
                vehicle = detection["box"]
                intersection = (max(0, min(box[2], vehicle[2]) - max(box[0], vehicle[0]))
                                * max(0, min(box[3], vehicle[3]) - max(box[1], vehicle[1])))
                coverage = intersection / slot_area
                if coverage > 0:
                    matches.append({**detection, "slot_coverage": coverage})
            coverage = max((m["slot_coverage"] for m in matches), default=0)
            # Marginal overlaps stay unknown instead of flickering to vacant.
            label = 1 if coverage >= self.overlap else None if coverage >= self.overlap / 2 else 0
            result = {"slot_id": slot_id, "box": box, "status": "unknown" if label is None else "ok",
                      "label": label, "class_name": "occupied" if label == 1 else "vacant" if label == 0 else "unknown",
                      "result": "Có xe" if label == 1 else "Không có xe" if label == 0 else "Chưa xác định",
                      "car_score": max((m["confidence"] for m in matches), default=0),
                      "slot_coverage": coverage, "detections": matches,
                      "threshold": self.confidence, "overlap_threshold": self.overlap,
                      "execution_target": "raspberry_pi", "model": "yolo", "run": self.model_path.name}
            if label is None:
                result["error"] = "Xe nằm sát ranh giới ROI; cần kiểm tra hoặc hiệu chỉnh vùng ô đỗ."
            results.append(result)
        return self._frame(image, camera, frame_id, results, detections, started)

    def _frame(self, image, camera, frame_id, results, detections, started):
        latency = round((time.perf_counter() - started) * 1000, 2)
        for result in results:
            result["latency_ms"] = latency
        return {"camera_id": camera.camera_id, "frame_id": frame_id, "execution_target": "raspberry_pi",
                "original_size": list(image.size), "complete": all(r["status"] == "ok" for r in results),
                "latency_ms": latency, "latency_scope": "full_frame", "model": self.model_path.name,
                "detections": detections, "results": results, "counts": {
                    "occupied": sum(r["label"] == 1 for r in results),
                    "vacant": sum(r["label"] == 0 for r in results),
                    "unknown": sum(r["label"] is None for r in results)}}
