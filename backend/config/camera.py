"""Load fixed-camera ROI configuration."""
import json
from pathlib import Path
from backend.schemas.camera import CameraConfig

def load_config(path):
    path = Path(path)
    return CameraConfig.model_validate(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None
