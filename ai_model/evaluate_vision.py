"""Audit raw single-view YOLO and optionally compare car presence to TinyML.

Presence metrics describe whether ANY car is visible, not per-slot occupancy or detection mAP.
This baseline bypasses the API's rotation voting and truncated-object count policy.
Weights must already exist. This command never starts the backend server.
"""
import argparse
import csv
import json
from pathlib import Path
import statistics
import time

from backend.model.inference import read_frame
from backend.config.vision import DEFAULT_VISION_MODEL

VEHICLES = {"car"}


def presence_metrics(rows):
    labeled = [r for r in rows if r.get("expected") is not None]
    tp = sum(r["expected"] == 1 and r["detected"] for r in labeled)
    tn = sum(r["expected"] == 0 and not r["detected"] for r in labeled)
    fp = sum(r["expected"] == 0 and r["detected"] for r in labeled)
    fn = sum(r["expected"] == 1 and not r["detected"] for r in labeled)
    return {"samples": len(labeled), "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "accuracy": (tp + tn) / len(labeled) if labeled else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-dir", type=Path, default=Path("test_image"))
    parser.add_argument("--models", type=Path, nargs="+", default=[DEFAULT_VISION_MODEL])
    parser.add_argument("--image-sizes", type=int, nargs="+", default=[640, 960])
    parser.add_argument("--confidences", type=float, nargs="+", default=[0.35, 0.15])
    parser.add_argument("--labels", type=Path, help="Optional JSON mapping filename to vehicle presence 0/1")
    parser.add_argument("--cnn-model-dir", type=Path, help="Optionally run local TinyML INT8 for comparison")
    parser.add_argument("--output-dir", type=Path, default=Path("ai_model/output/vision_audit"))
    args = parser.parse_args()
    paths = sorted(p for p in args.image_dir.iterdir() if p.is_file()
                   and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"})
    if not paths:
        parser.error("No images found")
    if any(not p.exists() for p in args.models):
        parser.error("Download model weights before running this audit")
    if any(s < 32 or s > 2048 or s % 32 for s in args.image_sizes):
        parser.error("Image sizes must be multiples of 32 between 32 and 2048")
    if any(not 0 < c <= 1 for c in args.confidences):
        parser.error("Confidence thresholds must be in (0, 1]")
    labels = json.loads(args.labels.read_text(encoding="utf-8")) if args.labels else {}
    if any(type(v) is not int or v not in {0, 1} for v in labels.values()):
        parser.error("Presence labels must be integer 0/1")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    images = [(p, read_frame(p.read_bytes())) for p in paths]
    rows, raw_outputs, summaries = [], [], []
    if args.cnn_model_dir:
        from backend.model.inference import ParkingPredictor
        cnn = ParkingPredictor(args.cnn_model_dir)
        for path, image in images:
            result = cnn.predict_pixels(cnn.preprocess(image), "int8", image.size)
            rows.append({"model": "tinyml_int8", "image_size": 64, "confidence": cnn.threshold,
                         "image": path.name, "expected": labels.get(path.name),
                         "detected": bool(result["label"]), "count": None,
                         "score": result["car_score"], "latency_ms": result["latency_ms"]})
        summaries.append({"model": "tinyml_int8", "note": "Center-cropped single-slot classifier; full scenes are outside its intended input.",
                          **presence_metrics(rows)})
    from backend.model.vision import VisionPredictor
    for model_path in args.models:
        predictor = VisionPredictor(model_path)
        for size in args.image_sizes:
            # Warm up before timing; model load/first inference are excluded from reported latencies.
            predictor.model.predict(source=images[0][1].convert("RGB"), imgsz=size, conf=min(args.confidences),
                                    device="cpu", verbose=False)
            for path, image in images:
                started = time.perf_counter()
                output = predictor.model.predict(source=image.convert("RGB"), imgsz=size,
                    conf=min(args.confidences), device="cpu", verbose=False)[0]
                latency = round((time.perf_counter() - started) * 1000, 2)
                raw = [{"class_name": output.names[int(c)].strip().casefold(), "confidence": s, "box": b}
                       for b, s, c in zip(output.boxes.xyxy.cpu().tolist(), output.boxes.conf.cpu().tolist(),
                                         output.boxes.cls.cpu().tolist())]
                raw_outputs.append({"model": model_path.name, "image_size": size, "image": path.name,
                                    "original_size": list(image.size), "all_classes": raw})
                for confidence in args.confidences:
                    vehicles = [d for d in raw if d["class_name"] in VEHICLES and d["confidence"] >= confidence]
                    rows.append({"model": model_path.name, "image_size": size, "confidence": confidence,
                                 "image": path.name, "expected": labels.get(path.name),
                                 "detected": bool(vehicles), "count": len(vehicles),
                                 "score": max((d["confidence"] for d in vehicles), default=0), "latency_ms": latency})
            for confidence in args.confidences:
                subset = [r for r in rows if r["model"] == model_path.name and r["image_size"] == size
                          and r["confidence"] == confidence]
                summary = {"model": model_path.name, "image_size": size, "confidence": confidence,
                           "median_latency_ms_pc": statistics.median(r["latency_ms"] for r in subset),
                           **presence_metrics(subset)}
                summaries.append(summary)
                print(json.dumps(summary), flush=True)
    report = {"note": "Exploratory evaluation on supplied images. Presence labels are manually reviewed. "
                      "These are not held-out accuracy, per-slot metrics, or detection mAP. "
                      "Thresholds derived from one low-confidence inference per image; latency is on this PC, not Pi.",
              "summaries": summaries, "results": rows, "raw_outputs": raw_outputs}
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (args.output_dir / "results.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Report: {(args.output_dir / 'report.json').resolve()}")


if __name__ == "__main__":
    main()
