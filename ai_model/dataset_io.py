"""Shared preprocessing and explicit labels for training and evaluation."""

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


CLASS_LABELS = {"vacant": 0, "occupied": 1}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def preprocess_image(path):
    """Center crop, bilinear resize, grayscale; model itself divides by 255."""
    with Image.open(path) as image:
        return preprocess_pil(image)


def preprocess_pil(image):
    """The same preprocessing for a file, upload, or a configured camera ROI."""
    image = ImageOps.exif_transpose(image).convert("L")
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    image = image.crop((left, top, left + side, top + side))
    image = image.resize((64, 64), Image.Resampling.BILINEAR)
    return np.asarray(image, dtype=np.uint8)[..., np.newaxis]


def load_dataset(directory):
    directory = Path(directory)
    images, labels, paths = [], [], []
    for name, label in CLASS_LABELS.items():
        folder = directory / name
        files = sorted(p for p in folder.rglob("*")
                       if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        if not files:
            raise ValueError(f"No images in {folder}. Expected vacant=0 and occupied=1.")
        for path in files:
            try:
                images.append(preprocess_image(path))
            except Exception as error:
                raise ValueError(f"Cannot read image {path}: {error}") from error
            labels.append(label)
            paths.append(str(path.resolve()))
        print(f"{directory.name}/{name}: {len(files)} images (label {label})")
    return np.stack(images), np.asarray(labels, dtype=np.float32), paths


def image_hashes(images):
    return [hashlib.sha256(image.tobytes()).hexdigest() for image in images]


def reject_overlap(first_hashes, second_hashes, description):
    count = len(set(first_hashes) & set(second_hashes))
    if count:
        raise ValueError(f"{description}: {count} identical preprocessed images overlap. "
                         "Move each original image/sequence to one split only.")
