"""Shared backend paths and limits."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_MODEL_DIR = PROJECT_ROOT / "ai_model" / "output" / "run_gpu01"
DEFAULT_ROI_CONFIG = PROJECT_ROOT / "config" / "parking.json"
