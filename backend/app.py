"""FastAPI gateway for wide-angle camera ROIs and ESP32 inference."""
import argparse
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.api.routes import router
from backend.config.camera import load_config
from backend.config.settings import PROJECT_ROOT, DEFAULT_MODEL_DIR, DEFAULT_ROI_CONFIG
from backend.model.inference import ParkingPredictor


def create_app(model_dir=None, threshold=None, esp32_url=None, roi_config=None, enable_reference=False):
    model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
    roi_config = Path(roi_config) if roi_config else DEFAULT_ROI_CONFIG

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

    service.include_router(router)

    # Mount only the dashboard folder. Training data and weights are not public assets.
    service.mount("/", StaticFiles(directory=PROJECT_ROOT / "dashboard", html=True), name="dashboard")
    return service


app = create_app()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--threshold", type=float, help="Override validation threshold (fallback: 0.75)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--esp32-url", help="Example: http://192.168.1.50")
    parser.add_argument("--roi-config", type=Path, default=DEFAULT_ROI_CONFIG)
    parser.add_argument("--enable-reference", action="store_true", help="Also load backend reference models when an ESP32 is configured")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.model_dir, args.threshold, args.esp32_url, args.roi_config, args.enable_reference), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
