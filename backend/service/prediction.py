"""Prediction target validation and camera frame orchestration."""
import uuid
from fastapi import HTTPException
from backend.model.inference import read_frame
from backend.service.esp32_client import DeviceError

def validate_target(predictor, model, target):
    if target == "esp32" and model != "int8":
        raise HTTPException(400, "ESP32 chỉ chạy INT8.")
    if model not in predictor.available_models:
        raise HTTPException(400, "Model không khả dụng.")
    if target == "esp32" and "esp32" not in predictor.status()["execution_targets"]:
        raise HTTPException(503, "ESP32 chưa được cấu hình. Khởi động với --esp32-url hoặc chọn Backend tham chiếu.")
    if target == "backend" and "backend" not in predictor.status()["execution_targets"]:
        raise HTTPException(503, "Backend tham chiếu chưa bật. Khởi động với --enable-reference để đối chiếu.")

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

