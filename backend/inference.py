"""FastAPI parking inference service, dashboard and Swagger UI."""

import base64
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import threading
import time
import warnings
import uuid



PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def read_frame(data):
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = 20_000_000
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(data)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP", "BMP"}:
                raise ValueError("Only JPG, PNG, WebP and BMP are supported")
            return ImageOps.exif_transpose(image).copy()


def resolve_threshold(model_dir, override=None):
    source = "configured"
    if override is None:
        report = model_dir / "validation" / "metrics.json"
        if report.is_file():
            override = json.loads(report.read_text(encoding="utf-8"))["recommended_int8_threshold_from_validation"]
            source = "validation"
        else:
            override, source = 0.75, "default"
    value = float(override)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Threshold must be finite and between 0 and 1")
    return value, source


class ParkingPredictor:
    def __init__(self, model_dir, threshold=None, esp32_url=None, reference_models=True):
        import numpy as np
        from PIL import Image
        from ai_model.dataset_io import preprocess_pil
        from backend.esp32_client import Esp32Client

        Image.MAX_IMAGE_PIXELS = 20_000_000
        self.np, self.Image, self.preprocess = np, Image, preprocess_pil
        self.device = Esp32Client(esp32_url) if esp32_url else None
        self.model_dir = Path(model_dir).resolve()
        self.threshold, self.threshold_source = resolve_threshold(self.model_dir, threshold)
        self.lock = threading.Lock()
        self.reference_models = reference_models
        self.keras_model, self.interpreter = None, None
        keras_path = self.model_dir / "parking_cnn.keras"
        int8_path = self.model_dir / "parking_cnn_int8.tflite"
        self.model_sha256 = hashlib.sha256(int8_path.read_bytes()).hexdigest() if int8_path.is_file() else None
        if reference_models:
            import tensorflow as tf
            # Reference tests run on CPU; the deployment path does not load TF.
            tf.config.set_visible_devices([], "GPU")
        if reference_models and keras_path.is_file():
            self.keras_model = tf.keras.models.load_model(keras_path, compile=False)
            if tuple(self.keras_model.input_shape[1:]) != (64, 64, 1) or self.keras_model.output_shape[-1] != 1:
                raise ValueError("Float model must accept 64x64x1 and return one sigmoid score")
        if reference_models and int8_path.is_file():
            self.interpreter = tf.lite.Interpreter(model_path=str(int8_path))
            self.interpreter.allocate_tensors()
            self.input = self.interpreter.get_input_details()[0]
            self.output = self.interpreter.get_output_details()[0]
            if (list(self.input["shape"]) != [1, 64, 64, 1]
                    or self.input["dtype"] != np.int8 or self.output["dtype"] != np.int8
                    or self.input["quantization"][0] <= 0 or self.output["quantization"][0] <= 0):
                raise ValueError("Invalid INT8 model shape, dtype, or quantization")
        if not self.available_models:
            raise FileNotFoundError(f"No parking_cnn.keras or parking_cnn_int8.tflite in {self.model_dir}")

    @property
    def available_models(self):
        return (["int8"] if self.interpreter is not None or (self.device and self.model_sha256) else []) + (["float"] if self.keras_model is not None else [])

    def status(self):
        return {"ready": True, "run": self.model_dir.name, "models": self.available_models,
                "threshold": self.threshold, "threshold_source": self.threshold_source,
                "max_upload_bytes": MAX_UPLOAD_BYTES,
                "execution_targets": (["backend"] if self.reference_models else []) + (["esp32"] if self.device and self.model_sha256 else [])}

    def predict(self, data, model_type, target="backend"):
        image = read_frame(data)
        return self.predict_pixels(self.preprocess(image), model_type, image.size, target)

    def predict_pixels(self, pixels, model_type, original_size, target="backend", slot_id="upload", request_id=None):
        from backend.esp32_client import DeviceError
        request_id = request_id or uuid.uuid4().hex
        if target not in {"backend", "esp32"}:
            raise ValueError("Unknown execution target")
        if target == "backend" and not self.reference_models:
            raise ValueError("Backend reference mode is disabled; use --enable-reference to enable it")
        if model_type not in self.available_models:
            raise ValueError("Model không khả dụng. Hãy chọn lại model.")
        if target == "esp32":
            if not self.device or not self.model_sha256:
                raise DeviceError("ESP32 chưa được cấu hình (--esp32-url) hoặc thiếu model INT8.")
            if model_type != "int8":
                raise ValueError("ESP32 chỉ chạy model INT8.")
            remote = self.device.predict(pixels, self.threshold, self.model_sha256, request_id, slot_id)
            return self.result(pixels, remote["car_score"], remote["latency_ms"], model_type,
                               original_size, target, slot_id, request_id)
        with self.lock:
            started = time.perf_counter()
            if model_type == "int8":
                scale, zero = self.input["quantization"]
                quantized = self.np.clip(self.np.rint(pixels.astype(self.np.float32) / scale) + zero,
                                         -128, 127).astype(self.np.int8)
                self.interpreter.set_tensor(self.input["index"], quantized[self.np.newaxis, ...])
                self.interpreter.invoke()
                raw = int(self.interpreter.get_tensor(self.output["index"]).reshape(-1)[0])
                scale, zero = self.output["quantization"]
                score = float(self.np.clip((raw - zero) * scale, 0, 1))
            else:
                output = self.keras_model(pixels[self.np.newaxis, ...].astype(self.np.float32), training=False)
                score = float(output.numpy().reshape(-1)[0])
            latency = (time.perf_counter() - started) * 1000
        return self.result(pixels, score, latency, model_type, original_size, target, slot_id, request_id)

    def result(self, pixels, score, latency, model_type, original_size, target, slot_id, request_id):
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise RuntimeError("Model returned an invalid probability")
        label = int(score >= self.threshold)
        preview = BytesIO()
        self.Image.fromarray(pixels[..., 0]).save(preview, format="PNG")
        return {"label": label, "class_name": "occupied" if label else "vacant",
                "result": "Có xe" if label else "Không có xe", "car_score": score,
                "threshold": self.threshold, "threshold_source": self.threshold_source,
                "model": model_type, "run": self.model_dir.name, "latency_ms": round(latency, 2),
                "original_size": list(original_size), "execution_target": target,
                "request_id": request_id, "slot_id": slot_id,
                "model_sha256": self.model_sha256 if model_type == "int8" else None,
                "input_preview": "data:image/png;base64," + base64.b64encode(preview.getvalue()).decode("ascii")}


