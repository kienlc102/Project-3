"""Select threshold on validation, evaluate held-out test, export alternate firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from ai_model.dataset_io import load_dataset, image_hashes, reject_overlap
from ai_model.evaluate_model import classification_metrics, predict_int8


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=Path("ai_model/output/run_camera8_ft02"))
    parser.add_argument("--parent-dir", type=Path, default=Path("ai_model/output/run_gpu01"))
    parser.add_argument("--dataset-dir", type=Path, default=Path("ai_model/dataset_camera8_finetune"))
    args = parser.parse_args()
    preparation = json.loads((args.dataset_dir / "camera8_manifest.json").read_text())
    for name, digest in preparation["parent_hashes"].items():
        if hashlib.sha256((args.parent_dir / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Original artifact changed: {name}")
    manifest = json.loads((args.model_dir / "dataset_manifest.json").read_text())
    parent = json.loads((args.parent_dir / "dataset_manifest.json").read_text())
    X_val, y_val, val_paths = load_dataset(args.dataset_dir / "val")
    reject_overlap(manifest["train_hashes"], image_hashes(X_val), "Validation vs fine-tune train")
    val_scores = predict_int8(args.model_dir / "parking_cnn_int8.tflite", X_val)
    # Threshold selection sees validation only. Test is loaded AFTER selection.
    candidates = [classification_metrics(y_val, val_scores, step / 100) for step in range(5, 100, 5)]
    best = max(candidates, key=lambda item: (item["f1_occupied"], item["precision_occupied"], -abs(item["threshold"] - .5)))
    threshold = best["threshold"]
    validation_dir = args.model_dir / "validation"
    validation_dir.mkdir(exist_ok=True)
    (validation_dir / "metrics.json").write_text(json.dumps({
        "recommended_int8_threshold_from_validation": threshold,
        "threshold_selection": "Maximum occupied F1 on validation only; precision breaks ties",
        "int8": best, "candidates": candidates,
    }, indent=2))
    X_test, y_test, test_paths = load_dataset(args.dataset_dir / "test")
    test_hashes = image_hashes(X_test)
    reject_overlap(manifest["train_hashes"] + manifest["val_hashes"], test_hashes, "Test vs fine-tune development")
    reject_overlap(parent["train_hashes"] + parent["val_hashes"], test_hashes, "Test vs parent development")
    new_scores = predict_int8(args.model_dir / "parking_cnn_int8.tflite", X_test)
    old_scores = predict_int8(args.parent_dir / "parking_cnn_int8.tflite", X_test)
    report = {
        "parent_model_sha256": hashlib.sha256((args.parent_dir / "parking_cnn_int8.tflite").read_bytes()).hexdigest(),
        "finetuned_model_sha256": hashlib.sha256((args.model_dir / "parking_cnn_int8.tflite").read_bytes()).hexdigest(),
        "test_dates": preparation["splits"]["test"]["dates"],
        "frame_splits": {name: {key: values[key] for key in ("assigned_frames", "labeled_frames", "patch_counts")}
                         for name, values in preparation["splits"].items()},
        "parent_int8_at_current_threshold": classification_metrics(y_test, old_scores, .6),
        "finetuned_int8_at_same_threshold": classification_metrics(y_test, new_scores, .6),
        "finetuned_int8_at_validation_threshold": classification_metrics(y_test, new_scores, threshold),
        "int8_model_bytes": (args.model_dir / "parking_cnn_int8.tflite").stat().st_size,
        "hardware_verified": False,
    }
    import tensorflow as tf
    interpreter = tf.lite.Interpreter(model_path=str(args.model_dir / "parking_cnn_int8.tflite"))
    interpreter.allocate_tensors()
    ops = sorted({op["op_name"] for op in interpreter._get_ops_details()} - {"DELEGATE"})
    supported = {"CONV_2D", "DEPTHWISE_CONV_2D", "MAX_POOL_2D", "MEAN", "FULLY_CONNECTED", "LOGISTIC"}
    if set(ops) - supported:
        raise ValueError(f"Fine-tuned model requires unsupported firmware operators: {ops}")
    report["firmware_operators"] = ops
    model = tf.keras.models.load_model(args.model_dir / "parking_cnn.keras", compile=False)
    report["parameters"] = model.count_params()
    float_scores = model.predict(X_test.astype(np.float32), batch_size=64, verbose=0).reshape(-1)
    report["finetuned_float_at_validation_threshold"] = classification_metrics(y_test, float_scores, threshold)
    report["float_int8_mean_absolute_score_difference"] = float(np.mean(np.abs(float_scores - new_scores)))
    import csv
    history = list(csv.DictReader((args.model_dir / "history.csv").open()))
    best_epoch = min(history, key=lambda row: float(row["val_loss"]))
    report["training"] = {"epochs_completed": len(history),
        "best_epoch_by_validation_loss": int(best_epoch["epoch"]) + 1,
        "best_validation_loss": float(best_epoch["val_loss"]), "parent_artifacts_unchanged": True}
    with (args.model_dir / "test_predictions.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path", "true_label", "old_int8_score", "new_int8_score", "new_float_score"])
        writer.writerows(zip(test_paths, y_test.astype(int), old_scores, new_scores, float_scores))
    test_frames = {patch["frame"] for patch in preparation["patches"] if patch["split"] == "test"}
    unlabeled_frames = set(preparation["splits"]["test"]["unlabeled_frames"])
    with (args.model_dir / "test_frames.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["frame_path", "has_official_labels"])
        writer.writerows((path, int(path not in unlabeled_frames)) for path in sorted(test_frames | unlabeled_frames))
    (args.model_dir / "comparison.json").write_text(json.dumps(report, indent=2))
    # Export a separate single-file firmware; do not replace the deployed model.
    template = Path("firmware_esp32/esp32_parking_main.cpp").read_text(encoding="utf-8")
    header = (args.model_dir / "model_data.h").read_text(encoding="utf-8")
    start = template.index("// ==========================================================================")
    end = template.index("#endif // PARKING_MODEL_DATA_H_", start) + len("#endif // PARKING_MODEL_DATA_H_")
    firmware = template[:start] + header + template[end:]
    firmware = re.sub(r"#define DEFAULT_CAR_THRESHOLD .*", f"#define DEFAULT_CAR_THRESHOLD {threshold:.2f}f", firmware)
    target = args.model_dir / "esp32_parking_camera8.cpp"
    target.write_text(firmware, encoding="utf-8")
    (args.model_dir / "COMPLETE.json").write_text(json.dumps({
        "status": "complete", "hardware_verified": False, "report": "comparison.json",
        "parent_artifacts_unchanged": True}, indent=2))
    print(json.dumps(report, indent=2), flush=True)
    print(f"Separate firmware: {target}", flush=True)


if __name__ == "__main__":
    main()
