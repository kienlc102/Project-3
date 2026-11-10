"""Camera configuration and frame prediction endpoints."""
from typing import Annotated, Literal
from urllib.parse import urlsplit
from urllib.request import urlopen
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from backend.api.uploads import read_upload
from backend.config.settings import MAX_UPLOAD_BYTES
from backend.service.prediction import process_frame
from backend.service.camera_capture import capture_local

router = APIRouter()

@router.get("/api/rois", tags=["Camera"])
def rois(request: Request):
    camera = request.app.state.camera
    return {"configured": camera is not None, "camera": camera.model_dump(exclude={"snapshot_url"}) if camera else None}

@router.post("/api/predict-frame", tags=["Camera"], summary="Crop configured ROIs from a wide-angle frame")
def predict_frame(request: Request, file: Annotated[UploadFile, File()],
                  target: Literal["esp32", "backend", "raspberry_pi"] = "esp32", model: Literal["int8", "float", "yolo"] = "int8"):
    return process_frame(request, read_upload(file), model, target)

@router.post("/api/predict-camera", tags=["Camera"], summary="Read the configured HTTP snapshot camera")
def predict_camera(request: Request, target: Literal["esp32", "backend", "raspberry_pi"] = "esp32"):
    camera = request.app.state.camera
    if camera is None:
        raise HTTPException(409, "Chưa có cấu hình camera.")
    if camera.capture_device is not None or camera.use_picamera2:
        return process_frame(request, capture_local(camera), "int8", target)
    if not camera.snapshot_url:
        raise HTTPException(409, "Chưa cấu hình nguồn ảnh: snapshot_url, capture_device hoặc use_picamera2.")
    if urlsplit(camera.snapshot_url).scheme not in {"http", "https"}:
        raise HTTPException(422, "Chỉ hỗ trợ HTTP(S) snapshot; chưa có adapter RTSP.")
    try:
        with urlopen(camera.snapshot_url, timeout=10) as response:
            data = response.read(MAX_UPLOAD_BYTES + 1)
    except OSError as error:
        raise HTTPException(502, "Không lấy được ảnh từ camera.") from error
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Ảnh camera vượt quá 10 MB.")
    return process_frame(request, data, "int8", target)

