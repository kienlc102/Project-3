"""Prepare the parking car detector and optionally export NCNN on the target Pi.

Example: python -m ai_model.prepare_vision_model --model parking-car --ncnn
"""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen

from backend.config.vision import (PARKING_CAR_DOWNLOAD, PARKING_CAR_FILENAME,
                                  PARKING_CAR_PROFILE, PARKING_CAR_REVISION,
                                  PARKING_CAR_SHA256, PARKING_CAR_SOURCE)


def prepare_parking_car(output_dir):
    destination = output_dir / PARKING_CAR_FILENAME
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != PARKING_CAR_SHA256:
            raise ValueError(f"Model checksum mismatch: {destination}. Keep custom weights under a different filename.")
    else:
        partial = destination.with_suffix(".pt.part")
        try:
            digest = hashlib.sha256()
            with urlopen(PARKING_CAR_DOWNLOAD, timeout=60) as response, partial.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    digest.update(chunk)
                    stream.write(chunk)
            if digest.hexdigest() != PARKING_CAR_SHA256:
                raise ValueError("Downloaded parking model checksum mismatch")
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
    print(f"Source: {PARKING_CAR_SOURCE}, revision {PARKING_CAR_REVISION}, weights CC-BY-4.0")
    print(f"SHA-256 verified: {PARKING_CAR_SHA256}")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=[PARKING_CAR_PROFILE, "yolo11n.pt", "yolo11s.pt", "yolo26n.pt", "yolo26s.pt"], default=PARKING_CAR_PROFILE)
    parser.add_argument("--output-dir", type=Path, default=Path("ai_model/output/vision"))
    parser.add_argument("--ncnn", action="store_true", help="Export on the target Raspberry Pi for ARM compatibility")
    parser.add_argument("--image-size", type=int, default=640)
    args = parser.parse_args()
    if args.image_size < 32 or args.image_size % 32:
        parser.error("--image-size must be a positive multiple of 32")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    from ultralytics import YOLO
    if args.model == PARKING_CAR_PROFILE:
        destination = prepare_parking_car(args.output_dir)
    else:
        destination = args.output_dir / args.model
    model = YOLO(str(destination), task="detect")
    print(f"Pretrained weights: {destination.resolve()}")
    if args.ncnn:
        model = YOLO(str(destination), task="detect")
        exported = model.export(format="ncnn", imgsz=args.image_size, device="cpu")
        print(f"NCNN model: {Path(exported).resolve()}")
    print("Use --vision-model with the weights file or exported NCNN directory to start the gateway.")


if __name__ == "__main__":
    main()
