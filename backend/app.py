"""FastAPI gateway for wide-angle camera ROIs and ESP32 inference."""
import argparse
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import uuid
from urllib.parse import urlsplit
from urllib.request import urlopen
from typing import Annotated, Literal
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.inference import ParkingPredictor, PROJECT_ROOT, MAX_UPLOAD_BYTES, read_frame
from backend.esp32_client import DeviceError
from backend.roi import load_config

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


def create_app(model_dir=None, threshold=None, esp32_url=None, roi_config=None, enable_reference=False):
    model_dir = Path(model_dir) if model_dir else PROJECT_ROOT / "ai_model" / "output" / "run_gpu01"
    roi_config = Path(roi_config) if roi_config else PROJECT_ROOT / "config" / "parking.json"

    @asynccontextmanager
    async def lifespan(app):
        app.state.predictor = ParkingPredictor(model_dir, threshold, esp32_url, enable_reference or not esp32_url)
        app.state.camera = load_config(roi_config)
        logging.getLogger("uvicorn.error").info("Models %s loaded; threshold=%s (%s)",
            app.state.predictor.available_models, app.state.predictor.threshold, app.state.predictor.threshold_source)
        yield
        app.state.predictor = None

    service = FastAPI(title="Wide-angle Parking Gateway", version="2.0.0",
                      description="Camera frame → fixed ROIs → ESP32 INT8 inference. Backend execution is a reference test mode.",
                      lifespan=lifespan)

    @service.get("/health", tags=["Status"])
    def health(request: Request):
        return {"status": "ok", "gateway_ready": request.app.state.predictor is not None,
                "esp32_configured": request.app.state.predictor.device is not None}

    @service.get("/api/status", tags=["Status"])
    def status(request: Request):
        result = request.app.state.predictor.status()
        camera = request.app.state.camera
        result.update({"camera_configured": camera is not None, "roi_count": len(camera.slots) if camera else 0})
        return result

    @service.get("/api/rois", tags=["Camera"])
    def rois(request: Request):
        camera = request.app.state.camera
        return {"configured": camera is not None, "camera": camera.model_dump(exclude={"snapshot_url"}) if camera else None}

    def read_upload(file):
        try:
            if file.size is not None and file.size > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "Ảnh vượt quá giới hạn 10 MB.")
            data = file.file.read(MAX_UPLOAD_BYTES + 1)
            if not data:
                raise HTTPException(422, "File ảnh rỗng. Hãy chọn một ảnh khác.")
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "Ảnh vượt quá giới hạn 10 MB.")
            return data
        finally:
            file.file.close()

    def validate_target(predictor, model, target):
        if target == "esp32" and model != "int8":
            raise HTTPException(400, "ESP32 chỉ chạy INT8.")
        if model not in predictor.available_models:
            raise HTTPException(400, "Model không khả dụng.")
        if target == "esp32" and "esp32" not in predictor.status()["execution_targets"]:
            raise HTTPException(503, "ESP32 chưa được cấu hình. Khởi động với --esp32-url hoặc chọn Backend tham chiếu.")
        if target == "backend" and "backend" not in predictor.status()["execution_targets"]:
            raise HTTPException(503, "Backend tham chiếu chưa bật. Khởi động với --enable-reference để đối chiếu.")

    @service.post("/api/predict", response_model=PredictionResponse, tags=["Prediction"],
                  summary="Upload ảnh một ô đỗ và dự đoán có xe / không có xe",
                  responses={413: {"description": "Ảnh vượt quá 10 MB"},
                             422: {"description": "Ảnh hoặc tham số không hợp lệ"}})
    def predict(request: Request,
                file: Annotated[UploadFile, File(description="JPG, PNG, WebP or BMP; at most 10 MB")],
                model: Annotated[Literal["int8", "float"], Query(description="Model inference format")] = "int8",
                target: Annotated[Literal["esp32", "backend"], Query(description="ESP32 production path or backend reference test")] = "esp32"):
        predictor = request.app.state.predictor
        data = read_upload(file)
        validate_target(predictor, model, target)
        try:
            return predictor.predict(data, model, target)
        except DeviceError as error:
            raise HTTPException(502, str(error)) from error
        except (ValueError, OSError, predictor.Image.DecompressionBombError,
                predictor.Image.DecompressionBombWarning) as error:
            raise HTTPException(422, "Ảnh không hợp lệ, không được hỗ trợ hoặc quá lớn.") from error
        except Exception as error:
            logging.getLogger("uvicorn.error").exception("Inference failed")
            raise HTTPException(500, "Không thể chạy model. Xem terminal backend.") from error

    def process_frame(request, data, model, target):
        predictor, camera = request.app.state.predictor, request.app.state.camera
        validate_target(predictor, model, target)
        if camera is None:
            raise HTTPException(409, "Chưa có cấu hình ROI. Tạo config/parking.json hoặc dùng --roi-config.")
        try:
            image = read_frame(data)
            crops = list(camera.crops(image))
        except (ValueError, OSError, predictor.Image.DecompressionBombError,
                predictor.Image.DecompressionBombWarning) as error:
            raise HTTPException(422, str(error)) from error
        frame_id, results, device_failed = uuid.uuid4().hex, [], False
        for slot_id, crop, box in crops:
            try:
                if device_failed:
                    raise DeviceError("ESP32 unavailable; remaining ROIs were not processed")
                result = predictor.predict_pixels(predictor.preprocess(crop), model, crop.size,
                                                  target, slot_id, frame_id)
                result.update({"status": "ok", "box": box})
            except Exception as error:
                device_failed = target == "esp32"
                result = {"slot_id": slot_id, "status": "unknown", "label": None,
                          "box": box, "error": str(error)}
            results.append(result)
        return {"camera_id": camera.camera_id, "frame_id": frame_id, "execution_target": target,
                "original_size": list(image.size), "complete": all(r["status"] == "ok" for r in results),
                "results": results, "counts": {
                    "occupied": sum(r.get("label") == 1 for r in results),
                    "vacant": sum(r.get("label") == 0 for r in results),
                    "unknown": sum(r["status"] == "unknown" for r in results)}}

    @service.post("/api/predict-frame", tags=["Camera"], summary="Crop configured ROIs from a wide-angle frame")
    def predict_frame(request: Request, file: Annotated[UploadFile, File()],
                      target: Literal["esp32", "backend"] = "esp32", model: Literal["int8", "float"] = "int8"):
        return process_frame(request, read_upload(file), model, target)

    @service.post("/api/predict-camera", tags=["Camera"], summary="Read the configured HTTP snapshot camera")
    def predict_camera(request: Request, target: Literal["esp32", "backend"] = "esp32"):
        camera = request.app.state.camera
        if camera is None or not camera.snapshot_url:
            raise HTTPException(409, "Chưa cấu hình snapshot_url của camera.")
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

    # Mount only the dashboard folder. Training data and weights are not public assets.
    service.mount("/", StaticFiles(directory=PROJECT_ROOT / "dashboard", html=True), name="dashboard")
    return service


app = create_app()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=PROJECT_ROOT / "ai_model" / "output" / "run_gpu01")
    parser.add_argument("--threshold", type=float, help="Override validation threshold (fallback: 0.75)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--esp32-url", help="Example: http://192.168.1.50")
    parser.add_argument("--roi-config", type=Path, default=PROJECT_ROOT / "config" / "parking.json")
    parser.add_argument("--enable-reference", action="store_true", help="Also load backend reference models when an ESP32 is configured")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.model_dir, args.threshold, args.esp32_url, args.roi_config, args.enable_reference), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
