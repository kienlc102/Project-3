"""Prepare Camera 8 crops with official labels and a parent-independent test set."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re

from PIL import Image

from ai_model.dataset_io import preprocess_pil
from backend.schemas.camera import CameraConfig


def parent_dates(manifest):
    return {re.search(r"20\d{2}-\d{2}-\d{2}", name).group()
            for key in ("train_paths", "val_paths") for name in manifest[key]
            if re.search(r"20\d{2}-\d{2}-\d{2}", name)}


def split_frames(frames, seen_dates):
    groups = defaultdict(list)
    for path in frames:
        groups[path.parent.parent.name].append(path)
    test_days = set(groups) - seen_dates
    if not test_days:
        raise ValueError("No dates unseen by the parent model remain for independent test")
    development_days = sorted(set(groups) - test_days)
    target = sum(len(groups[date]) for date in development_days) * .2
    weather = {date: {p.parent.parent.parent.name for p in group} for date, group in groups.items()}
    choices = []
    for count in range(1, len(development_days)):
        # Daily groups have similar sizes; a bounded search around 20% is enough.
        if abs(count - len(development_days) * .2) > 2:
            continue
        for choice in itertools.combinations(development_days, count):
            train = set(development_days) - set(choice)
            if set.union(*(weather[d] for d in choice)) != {"SUNNY", "RAINY", "OVERCAST"}:
                continue
            if set.union(*(weather[d] for d in train)) != {"SUNNY", "RAINY", "OVERCAST"}:
                continue
            choices.append((abs(sum(len(groups[d]) for d in choice) - target), choice))
    if not choices:
        raise ValueError("Cannot construct weather-diverse day-disjoint train/validation")
    val_days = set(min(choices)[1])
    dates = {"test": test_days, "val": val_days,
             "train": set(development_days) - val_days}
    return {split: sorted(p for date in days for p in groups[date]) for split, days in dates.items()}


def prepare(source, labels_file, roi_file, parent_dir, destination):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Refusing to overwrite existing dataset: {destination}")
    parent_manifest = json.loads((parent_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    seen = parent_dates(parent_manifest)
    frames = sorted(source.rglob("camera8/*.jpg"))
    if not frames:
        raise ValueError("No camera8 full frames found")
    camera = CameraConfig.model_validate(json.loads(roi_file.read_text(encoding="utf-8")))
    if camera.camera_id != "cnr_camera8" or (camera.reference_width, camera.reference_height) != (1000, 750):
        raise ValueError("Expected Camera 8 ROI configuration at 1000x750")
    labels = {}
    with labels_file.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["camera"] != "08":
                continue
            key = (row["datetime"].replace(".", ""), "slot_" + row["slot_id"])
            label = int(row["occupancy"])
            if label not in (0, 1) or (key in labels and labels[key] != label):
                raise ValueError(f"Invalid/conflicting official label: {key}")
            labels[key] = label
    partitions = split_frames(frames, seen)
    manifest = {"source": str(source.resolve()), "official_labels": str(labels_file.resolve()),
                "official_labels_sha256": hashlib.sha256(labels_file.read_bytes()).hexdigest(),
                "roi": camera.model_dump(), "test_policy": "All capture dates unseen in parent train/val across all cameras",
                "parent_seen_dates": sorted(seen), "parent_hashes": {}, "splits": {}, "patches": []}
    for name in ("parking_cnn.keras", "parking_cnn_int8.tflite", "model_data.h"):
        manifest["parent_hashes"][name] = hashlib.sha256((parent_dir / name).read_bytes()).hexdigest()
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    # Keep test untouched; remove exact preprocessed duplicates from development.
    for split in ("test", "val", "train"):
        counts = Counter()
        skipped, duplicates, labeled_frames = [], 0, 0
        for frame in partitions[split]:
            slot_ids = [slot.id for slot in camera.slots]
            if any((frame.stem, slot) not in labels for slot in slot_ids):
                skipped.append(str(frame.resolve()))
                continue  # Never invent labels for unannotated frames.
            labeled_frames += 1
            with Image.open(frame) as image:
                if image.size != (1000, 750):
                    raise ValueError(f"Wrong full-frame resolution: {frame}")
                for slot_id, crop, box in camera.crops(image):
                    pixels = preprocess_pil(crop)
                    digest = hashlib.sha256(pixels.tobytes()).hexdigest()
                    if digest in hashes and hashes[digest] != split:
                        duplicates += 1
                        continue
                    hashes[digest] = split
                    label = labels[(frame.stem, slot_id)]
                    name = "occupied" if label else "vacant"
                    output = destination / split / name / f"{frame.stem}_{slot_id}.png"
                    output.parent.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(pixels[..., 0]).save(output)
                    counts[name] += 1
                    manifest["patches"].append({"split": split, "frame": str(frame.resolve()),
                        "slot_id": slot_id, "label": label, "box": box, "sha256": digest,
                        "path": str(output.resolve())})
        if not counts["occupied"] or not counts["vacant"]:
            raise ValueError(f"Split {split} is missing a class")
        manifest["splits"][split] = {"dates": sorted({p.parent.parent.name for p in partitions[split]}),
            "assigned_frames": len(partitions[split]), "labeled_frames": labeled_frames,
            "unlabeled_frames": skipped, "duplicate_crops_excluded": duplicates, "patch_counts": dict(counts)}
        print(split, json.dumps(manifest["splits"][split] | {"unlabeled_frames": len(skipped)}), flush=True)
    (destination / "camera8_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Prepared {destination}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("test_image/CNR-EXT_FULL_IMAGE_1000x750"))
    parser.add_argument("--labels", type=Path, default=Path("ai_model/raw_data/CNRPark+EXT.csv"))
    parser.add_argument("--roi", type=Path, default=Path("config/parking.json"))
    parser.add_argument("--parent-dir", type=Path, default=Path("ai_model/output/run_gpu01"))
    parser.add_argument("--destination", type=Path, default=Path("ai_model/dataset_camera8_finetune"))
    args = parser.parse_args()
    prepare(args.source, args.labels, args.roi, args.parent_dir, args.destination)


if __name__ == "__main__":
    main()
