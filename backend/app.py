"""FastAPI parking gateway: ESP32 TinyML or camera-only YOLO on Raspberry Pi."""
import argparse
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.api.routes import router
from backend.config.camera import load_config
from backend.config.settings import PROJECT_ROOT, DEFAULT_MODEL_DIR, DEFAULT_ROI_CONFIG
from backend.config.vision import DEFAULT_VISION_EDGE_MARGIN, DEFAULT_VISION_ROTATIONS, parse_rotations
from backend.model.inference import ParkingPredictor
from backend.model.vision import VisionPredictor


def create_app(model_dir=None, threshold=None, esp32_url=None, roi_config=None, enable_reference=False,
               vision_model=None, vision_confidence=0.75, vision_overlap=0.25, vision_image_size=640,
               vision_rotations=DEFAULT_VISION_ROTATIONS, vision_edge_margin=DEFAULT_VISION_EDGE_MARGIN):
    model_dir = Path(model_dir) if model_dir else DEFAULT_MODEL_DIR
    roi_config = Path(roi_config) if roi_config else DEFAULT_ROI_CONFIG

    @asynccontextmanager
    async def lifespan(app):
        load_cnn = bool(esp32_url or enable_reference or not vision_model)
        load_reference = enable_reference or (not esp32_url and not vision_model)
        app.state.predictor = (ParkingPredictor(model_dir, threshold, esp32_url,
                                               load_reference) if load_cnn else None)
        app.state.vision = (VisionPredictor(vision_model, vision_confidence, vision_overlap, vision_image_size,
                                          vision_rotations, vision_edge_margin)
                            if vision_model else None)
        app.state.camera = load_config(roi_config)
        logging.getLogger("uvicorn.error").info("Inference enabled: CNN=%s, vision=%s",
            app.state.predictor is not None, app.state.vision is not None)
        yield
        app.state.predictor = None
        app.state.vision = None

    service = FastAPI(title="Wide-angle Parking Gateway", version="2.0.0",
                      description="ESP32 INT8, backend reference tests, or camera-only YOLO inference on Raspberry Pi.",
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
    parser.add_argument("--enable-reference", action="store_true", help="Load CNN on the backend, including alongside YOLO or ESP32, for image API tests")
    parser.add_argument("--vision-model", type=Path, help="Use parking-car for the overhead car detector, or a local .pt file / NCNN directory")
    parser.add_argument("--vision-confidence", type=float, default=0.75, help="Vehicle detection confidence, independent of the CNN threshold")
    parser.add_argument("--vision-overlap", type=float, default=0.25, help="Minimum fraction of a slot covered by a vehicle box")
    parser.add_argument("--vision-image-size", type=int, default=640, help="Input size, multiple of 32; must match NCNN export")
    parser.add_argument("--vision-rotations", type=parse_rotations, default=DEFAULT_VISION_ROTATIONS,
                        help="Comma-separated quarter turns for class voting; use 0 for one pass")
    parser.add_argument("--vision-edge-margin", type=float, default=DEFAULT_VISION_EDGE_MARGIN,
                        help="Exclude boxes within this many pixels of an image edge from image counts; 0 includes them. ROI occupancy is unaffected.")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(args.model_dir, args.threshold, args.esp32_url, args.roi_config, args.enable_reference,
                          args.vision_model, args.vision_confidence, args.vision_overlap, args.vision_image_size,
                          args.vision_rotations, args.vision_edge_margin),
                host=args.host, port=args.port)


if __name__ == "__main__":
    main()
