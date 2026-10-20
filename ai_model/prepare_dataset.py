"""Copy parking patches into train/val/test, grouped by capture date."""

import argparse
import json
import random
import re
import shutil
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CLASS_ALIASES = {"free": 0, "vacant": 0, "busy": 1, "occupied": 1}


def collect_records(source, label_files=None):
    source = source.resolve()
    records = {}
    if label_files:
        for label_file in label_files:
            for line_number, line in enumerate(label_file.read_text(encoding="utf-8-sig").splitlines(), 1):
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                try:
                    name, label_text = line.rsplit(maxsplit=1)
                    label = int(label_text)
                    path = (source / name).resolve()
                    if label not in (0, 1) or not path.is_relative_to(source) or not path.is_file():
                        raise ValueError("label must be 0/1 and image path must exist inside source")
                    if path in records and records[path] != label:
                        raise ValueError("conflicting labels for the same image")
                    records[path] = label
                except ValueError as error:
                    raise ValueError(f"{label_file}:{line_number}: {error}") from error
    else:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            labels = {CLASS_ALIASES[part.lower()] for part in path.relative_to(source).parts[:-1]
                      if part.lower() in CLASS_ALIASES}
            if len(labels) != 1:
                raise ValueError(f"Cannot infer class for {path}; supply --labels or class folders.")
            records[path.resolve()] = labels.pop()
    if not records:
        raise ValueError(f"No images found in {source}")
    return records


def prepare_dataset(source, destination, label_files=None, seed=42, max_per_class_per_day=None):
    source, destination = source.resolve(), destination.resolve()
    if not source.is_dir():
        raise ValueError(f"Missing source folder: {source}")
    if destination == source or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Source and destination must be separate folders, neither containing the other.")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Destination is not empty: {destination}")
    records = collect_records(source, label_files)
    groups = {}
    for path, label in records.items():
        match = re.search(r"(?<!\d)(20\d{2})-?(\d{2})-?(\d{2})(?!\d)", path.relative_to(source).as_posix())
        if not match:
            raise ValueError(f"No capture date YYYY-MM-DD or YYYYMMDD in path: {path}")
        date = "-".join(match.groups())
        groups.setdefault(date, []).append((path, label))
    if len(groups) < 3:
        raise ValueError("Need at least 3 capture dates for independent train/val/test. "
                         "Use CNR-EXT or manually split independent parking-event groups.")
    if max_per_class_per_day is not None:
        if max_per_class_per_day < 1:
            raise ValueError("max_per_class_per_day must be positive")
        sampler = random.Random(seed)
        for date in sorted(groups):
            selected = []
            for label in (0, 1):
                items = sorted(item for item in groups[date] if item[1] == label)
                sampler.shuffle(items)
                selected.extend(items[:max_per_class_per_day])
            groups[date] = selected
    dates = sorted(groups)
    random.Random(seed).shuffle(dates)
    n_val = max(1, round(len(dates) * 0.15))
    n_test = max(1, round(len(dates) * 0.15))
    split_dates = {"test": dates[:n_test], "val": dates[n_test:n_test + n_val],
                   "train": dates[n_test + n_val:]}
    summary = {"seed": seed, "source": str(source), "grouping": "capture date across all cameras",
               "max_per_class_per_day": max_per_class_per_day, "splits": {}}
    for split, selected_dates in split_dates.items():
        items = [item for date in selected_dates for item in groups[date]]
        counts = {name: sum(label == value for _, label in items)
                  for name, value in (("vacant", 0), ("occupied", 1))}
        if not all(counts.values()):
            raise ValueError(f"{split} lacks a class; choose another seed or a more diverse dataset.")
        summary["splits"][split] = {"dates": sorted(selected_dates), "counts": counts}
    destination.mkdir(parents=True, exist_ok=True)
    for split, selected_dates in split_dates.items():
        for date in selected_dates:
            for path, label in groups[date]:
                target = destination / split / ("occupied" if label else "vacant") / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    (destination / "split_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--labels", type=Path, nargs="+", help="CNR-EXT lists, each line: relative/image.jpg 0_or_1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-per-class-per-day", type=int,
                        help="Optional random cap per class/date, e.g. 100 for an initial experiment")
    args = parser.parse_args()
    prepare_dataset(args.source, args.destination, args.labels, args.seed, args.max_per_class_per_day)


if __name__ == "__main__":
    main()
