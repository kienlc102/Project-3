"""Response for whole-image vehicle detection without parking ROI configuration."""
from typing import Literal

from pydantic import BaseModel, Field


class RawDetection(BaseModel):
    box: list[float] = Field(min_length=4, max_length=4, description="Pixel coordinates [x1, y1, x2, y2]")
    confidence: float = Field(ge=0, le=1)
    class_name: str
    support_views: int | None = Field(default=None, ge=1)
    class_votes: dict[str, float] | None = None


class ViewDetection(RawDetection):
    rotation: Literal[0, 90, 180, 270]


class RejectedDetection(RawDetection):
    reason: Literal["ambiguous_class", "insufficient_views", "below_confidence", "truncated_at_border"]


class VehicleDetection(RawDetection):
    class_name: Literal["car"]


class YoloDiagnostics(BaseModel):
    reason: Literal["vehicles_detected", "vehicles_filtered", "only_non_vehicle_detections", "no_detections"]
    vehicle_classes: list[str]
    raw_detections: list[RawDetection]
    view_detections: list[ViewDetection] | None = None
    rejected_detections: list[RejectedDetection] | None = None
    rotations: list[int] | None = None
    min_support_views: int | None = None
    candidate_confidence: float | None = None
    edge_margin_px: float | None = None


class YoloDetectionResponse(BaseModel):
    request_id: str
    execution_target: Literal["raspberry_pi"]
    model: Literal["yolo"]
    run: str
    original_size: list[int] = Field(min_length=2, max_length=2)
    confidence_threshold: float = Field(gt=0, le=1)
    detected: bool
    vehicle_count: int = Field(ge=0)
    detections: list[VehicleDetection]
    latency_ms: float = Field(ge=0)
    latency_scope: Literal["full_frame"]
    diagnostics: YoloDiagnostics | None = None
