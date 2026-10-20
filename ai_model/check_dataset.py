"""Validate train/val/test image loading, labels, and exact cross-split duplicates."""

import argparse
from itertools import combinations
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=Path("dataset"))
    args = parser.parse_args()
    from dataset_io import load_dataset, image_hashes, reject_overlap

    splits = {}
    for split in ("train", "val", "test"):
        images, labels, _ = load_dataset(args.dataset_dir / split)
        hashes = image_hashes(images)
        by_label = {label: [h for h, y in zip(hashes, labels) if y == label] for label in (0, 1)}
        reject_overlap(by_label[0], by_label[1], f"{split}: conflicting labels")
        splits[split] = hashes
        print(f"{split}: shape={images.shape}, dtype={images.dtype}, "
              f"pixel range={images.min()}..{images.max()}")
    for first, second in combinations(splits, 2):
        reject_overlap(splits[first], splits[second], f"{first} vs {second}")
    print("PASS: readable images, both labels in every split, no exact cross-split duplicates.")
    print("Still check grouping manually: nearby frames and the same parking event must stay together.")


if __name__ == "__main__":
    main()
