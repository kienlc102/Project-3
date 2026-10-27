"""Prediction API response schema."""
from typing import Literal
from pydantic import BaseModel, Field

class PredictionResponse(BaseModel):
    label: Literal[0, 1]
    class_name: Literal["occupied", "vacant"]
    result: str
    car_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    threshold_source: Literal["configured", "validation", "default"]
    model: Literal["int8", "float"]
    run: str
    latency_ms: float
    original_size: list[int]
    input_preview: str
    execution_target: Literal["backend", "esp32"]
    request_id: str
    slot_id: str
    model_sha256: str | None

