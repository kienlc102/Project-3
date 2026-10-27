"""Gateway health and runtime status endpoints."""
from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/health", tags=["Status"])
def health(request: Request):
    return {"status": "ok", "gateway_ready": request.app.state.predictor is not None,
            "esp32_configured": request.app.state.predictor.device is not None}

@router.get("/api/status", tags=["Status"])
def status(request: Request):
    result = request.app.state.predictor.status()
    camera = request.app.state.camera
    result.update({"camera_configured": camera is not None, "roi_count": len(camera.slots) if camera else 0})
    return result

