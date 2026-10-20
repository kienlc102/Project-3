"""Fixed-camera rectangular ROIs, scaled from a known reference resolution."""

import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Slot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class CameraConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camera_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    reference_width: int = Field(gt=0)
    reference_height: int = Field(gt=0)
    snapshot_url: str | None = None
    slots: list[Slot] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_slots(self):
        if len({slot.id for slot in self.slots}) != len(self.slots):
            raise ValueError("Slot IDs must be unique")
        for slot in self.slots:
            if slot.x + slot.width > self.reference_width or slot.y + slot.height > self.reference_height:
                raise ValueError(f"ROI {slot.id} is outside the reference image")
        return self

    def crops(self, image):
        width, height = image.size
        if abs((width / height) / (self.reference_width / self.reference_height) - 1) > 0.01:
            raise ValueError("Frame aspect ratio differs from ROI reference; recalibrate the camera configuration")
        for slot in self.slots:
            left = round(slot.x * width / self.reference_width)
            top = round(slot.y * height / self.reference_height)
            right = round((slot.x + slot.width) * width / self.reference_width)
            bottom = round((slot.y + slot.height) * height / self.reference_height)
            if right <= left or bottom <= top:
                raise ValueError(f"ROI {slot.id} becomes empty at this resolution")
            yield slot.id, image.crop((left, top, right, bottom)), [left, top, right, bottom]


def load_config(path):
    path = Path(path)
    return CameraConfig.model_validate(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None
