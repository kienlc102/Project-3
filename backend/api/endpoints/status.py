"""Gateway health and runtime status endpoints."""
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/health", tags=["Status"])
def health(request: Request):
    predictor, vision = request.app.state.predictor, request.app.state.vision
    return {"status": "ok", "gateway_ready": predictor is not None or vision is not None,
            "esp32_configured": predictor is not None and predictor.device is not None,
            "vision_configured": vision is not None}

@router.get("/api/status", tags=["Status"])
def status(request: Request):
    predictor, vision = request.app.state.predictor, request.app.state.vision
    result = predictor.status() if predictor else vision.status()
    if predictor and vision:
        vision_status = vision.status()
        result["models"] = result["models"] + vision_status["models"]
        result["execution_targets"] = result["execution_targets"] + ["raspberry_pi"]
        result["vision"] = vision_status["vision"]
    result["default_target"] = "esp32" if "esp32" in result["execution_targets"] else result["execution_targets"][0]
    camera = request.app.state.camera
    result.update({"camera_configured": camera is not None, "roi_count": len(camera.slots) if camera else 0})
    return result

