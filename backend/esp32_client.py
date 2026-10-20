"""HTTP transport: exactly 4096 raw grayscale pixels, never a JPEG/video stream."""

import json
import math
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class DeviceError(RuntimeError):
    pass


class Esp32Client:
    def __init__(self, base_url, timeout=10):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("ESP32 URL must be an HTTP(S) base URL")
        self.base_url, self.timeout = base_url.rstrip("/"), timeout

    def predict(self, pixels, threshold, model_sha256, request_id, slot_id):
        data = pixels.tobytes()
        if pixels.shape != (64, 64, 1) or len(data) != 4096 or str(pixels.dtype) != "uint8":
            raise ValueError("ESP32 input must be uint8 64x64x1")
        request = Request(self.base_url + "/infer", data=data, headers={
            "Content-Type": "application/octet-stream", "X-Threshold": str(threshold),
            "X-Model-Sha256": model_sha256, "X-Request-Id": request_id, "X-Slot-Id": slot_id,
        })
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(16385))
            score, latency = float(payload["car_score"]), float(payload["latency_ms"])
            response_threshold = float(payload["threshold"])
            if (payload.get("request_id") != request_id or payload.get("slot_id") != slot_id
                    or payload.get("model_sha256") != model_sha256
                    or not math.isfinite(score) or not 0 <= score <= 1
                    or not math.isfinite(latency) or latency < 0
                    or payload.get("label") != int(score >= threshold)
                    or not math.isfinite(response_threshold) or abs(response_threshold - threshold) > 1e-5):
                raise ValueError("Device response identity, threshold or score mismatch")
            return {"car_score": score, "latency_ms": latency}
        except (URLError, HTTPError, TimeoutError, OSError, KeyError, TypeError, ValueError) as error:
            raise DeviceError(f"ESP32 inference unavailable or invalid response: {error}") from error
