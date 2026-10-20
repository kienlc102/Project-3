"""Evaluate float and INT8 models at a fixed threshold, or predict one image."""

import argparse
import csv
import json
import math
from pathlib import Path


def classification_metrics(labels, probabilities, threshold):
    tp = tn = fp = fn = 0
    for label, score in zip(labels, probabilities):
        prediction = score >= threshold
        if label == 1:
            tp += int(prediction)
            fn += int(not prediction)
        else:
            fp += int(prediction)
            tn += int(not prediction)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "threshold": threshold,
        "samples": tp + tn + fp + fn,
        "confusion_matrix": {"TN": tn, "FP": fp, "FN": fn, "TP": tp},
        "accuracy": (tp + tn) / (tp + tn + fp + fn),
        "precision_occupied": precision,
        "recall_occupied": recall,
        "f1_occupied": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
    }


def predict_int8(model_path, images):
    import numpy as np
    import tensorflow as tf

    interpreter = tf.lite.Interpreter(model_path=str(model_path))
    interpreter.allocate_tensors()
    input_info = interpreter.get_input_details()[0]
    output_info = interpreter.get_output_details()[0]
    if input_info["dtype"] != np.int8 or output_info["dtype"] != np.int8:
        raise ValueError("Expected INT8 model input and output.")
    if list(input_info["shape"]) != [1, 64, 64, 1]:
        raise ValueError(f"Unexpected input shape: {input_info['shape']}")
    in_scale, in_zero = input_info["quantization"]
    out_scale, out_zero = output_info["quantization"]
    if in_scale <= 0 or out_scale <= 0:
        raise ValueError("Invalid quantization scales.")
    scores = []
    for image in images:
        # Input remains 0..255 because Rescaling is INSIDE the trained model.
        quantized = np.clip(np.rint(image.astype(np.float32) / in_scale) + in_zero,
                            -128, 127).astype(np.int8)
        interpreter.set_tensor(input_info["index"], quantized[np.newaxis, ...])
        interpreter.invoke()
        raw = int(interpreter.get_tensor(output_info["index"]).reshape(-1)[0])
        scores.append(float(np.clip((raw - out_zero) * out_scale, 0, 1)))
    return np.asarray(scores)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=Path("output"))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--data-dir", type=Path, help="Split directory containing vacant/ and occupied/")
    source.add_argument("--image", type=Path, help="One image containing one parking space")
    parser.add_argument("--threshold", type=float, required=True,
                        help="Choose on validation, then keep fixed for test")
    parser.add_argument("--report-dir", type=Path, default=Path("evaluation"))
    parser.add_argument("--split", choices=["val", "test"], default="test",
                        help="val allows validation images; test also rejects validation overlap")
    args = parser.parse_args()
    if not math.isfinite(args.threshold) or not 0 <= args.threshold <= 1:
        parser.error("--threshold must be a finite value between 0 and 1")

    import numpy as np
    import tensorflow as tf
    from dataset_io import load_dataset, preprocess_image, image_hashes, reject_overlap

    if args.image:
        images = preprocess_image(args.image)[np.newaxis, ...]
        paths, labels = [str(args.image.resolve())], None
    else:
        images, labels, paths = load_dataset(args.data_dir)
        manifest_path = args.model_dir / "dataset_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            reject_overlap(manifest["train_hashes"], image_hashes(images), "Evaluation vs train")
            # Validation is allowed for selecting the threshold. Test must be disjoint.
            if args.split == "test":
                reject_overlap(manifest["val_hashes"], image_hashes(images), "Evaluation vs validation")
        else:
            raise ValueError("Missing dataset_manifest.json; use the updated training script first.")

    model = tf.keras.models.load_model(args.model_dir / "parking_cnn.keras", compile=False)
    float_scores = model.predict(images.astype(np.float32), batch_size=32, verbose=0).reshape(-1)
    int8_path = args.model_dir / "parking_cnn_int8.tflite"
    int8_scores = predict_int8(int8_path, images)
    if not np.all(np.isfinite(float_scores)) or not np.all(np.isfinite(int8_scores)):
        raise ValueError("Model produced non-finite scores.")
    if args.image:
        for name, scores in (("float", float_scores), ("int8", int8_scores)):
            label = int(scores[0] >= args.threshold)
            print(f"{name}: score={scores[0]:.4f}, label={label} ({'occupied' if label else 'vacant'})")
        return

    report = {
        "data_dir": str(args.data_dir.resolve()),
        "float": classification_metrics(labels, float_scores, args.threshold),
        "int8": classification_metrics(labels, int8_scores, args.threshold),
        "int8_model_bytes": int8_path.stat().st_size,
        "mean_absolute_score_difference": float(np.mean(np.abs(float_scores - int8_scores))),
        "prediction_disagreements": int(np.sum((float_scores >= args.threshold) != (int8_scores >= args.threshold))),
    }
    if args.split == "val":
        candidates = [classification_metrics(labels, int8_scores, step / 100)
                      for step in range(5, 100, 5)]
        best = max(candidates, key=lambda item: (item["f1_occupied"], item["precision_occupied"],
                                               -abs(item["threshold"] - 0.5)))
        report["recommended_int8_threshold_from_validation"] = best["threshold"]
        report["threshold_selection"] = "Maximize occupied F1 on validation grid 0.05..0.95; precision breaks ties"
    args.report_dir.mkdir(parents=True, exist_ok=True)
    if args.split == "val":
        with (args.report_dir / "threshold_candidates.csv").open("w", newline="", encoding="utf-8") as stream:
            fields = ["threshold", "accuracy", "precision_occupied", "recall_occupied", "f1_occupied", "false_positive_rate"]
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(candidates)
    (args.report_dir / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (args.report_dir / "predictions.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["path", "true_label", "float_score", "int8_score", "float_label", "int8_label", "int8_correct"])
        for path, label, fs, qs in zip(paths, labels, float_scores, int8_scores):
            writer.writerow([path, int(label), float(fs), float(qs), int(fs >= args.threshold),
                             int(qs >= args.threshold), int((qs >= args.threshold) == label)])
    print(json.dumps(report, indent=2))
    print(f"Reports: {args.report_dir.resolve()}")


if __name__ == "__main__":
    main()
