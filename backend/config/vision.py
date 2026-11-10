"""Pinned camera model for car detection from elevated/overhead viewpoints."""
from pathlib import Path

from backend.config.settings import PROJECT_ROOT

PARKING_CAR_PROFILE = "parking-car"
PARKING_CAR_FILENAME = "geotrax_hbb_yolov8s_1920_v1.pt"
DEFAULT_VISION_MODEL = PROJECT_ROOT / "ai_model" / "output" / "vision" / PARKING_CAR_FILENAME
PARKING_CAR_REVISION = "d273ec3b92b40befb3a8e58520559d5b98dc1b43"
PARKING_CAR_SHA256 = "7d462ae523b15f3679a83f74ab08aa79d2978f319ca2f0cf2892fbbb60df79da"
PARKING_CAR_SOURCE = "https://huggingface.co/rfonod/geo-trax"
PARKING_CAR_DOWNLOAD = f"{PARKING_CAR_SOURCE}/resolve/{PARKING_CAR_REVISION}/{PARKING_CAR_FILENAME}"
DEFAULT_VISION_ROTATIONS = (0, 90, 180, 270)
DEFAULT_VISION_EDGE_MARGIN = 1.0


def parse_rotations(value):
    rotations = tuple(int(angle.strip()) for angle in value.split(","))
    if not rotations or len(set(rotations)) != len(rotations) or any(angle not in (0, 90, 180, 270) for angle in rotations):
        raise ValueError("Use unique comma-separated angles from 0,90,180,270")
    return rotations


def resolve_vision_model(value):
    return DEFAULT_VISION_MODEL if str(value) == PARKING_CAR_PROFILE else Path(value)
