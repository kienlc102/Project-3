"""HTTP transport: exactly 4096 raw grayscale pixels, never a JPEG/video stream."""

import json
import math
import logging
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class DeviceError(RuntimeError):
    pass


class Esp32Client:
    def __init__(self, base_url, timeout=10):
        self.auto = base_url == "auto"
        parsed = urlsplit(base_url) if not self.auto else None
        if parsed and (parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment):
            raise ValueError("ESP32 URL must be an HTTP(S) base URL")
        self.base_url, self.timeout = (None if self.auto else base_url.rstrip("/")), timeout
        self.lock = threading.Lock()
        self.discovered_at = 0
        self.stop_discovery = threading.Event()
        self.discovery_thread = None
        self.last_discovery_error = None

    def start_discovery(self, model_sha256):
        if not self.auto or self.discovery_thread:
            return
        self.stop_discovery.clear()

        def monitor():
            from backend.service.esp32_discovery import check_device, discover_device, DiscoveryError
            while not self.stop_discovery.is_set():
                # One owner of discovery/inference at a time; no races with a changed IP.
                if self.lock.acquire(timeout=1):
                    try:
                        if not self.base_url or not check_device(self.base_url, model_sha256):
                            self.base_url = None
                            self.base_url = discover_device(model_sha256)
                            logging.getLogger("uvicorn.error").info("ESP32 discovered: %s", self.base_url)
                        self.discovered_at = time.monotonic()
                        self.last_discovery_error = None
                    except DiscoveryError as error:
                        message = str(error)
                        if self.last_discovery_error != message:
                            logging.getLogger("uvicorn.error").warning("ESP32 discovery: %s", message)
                        self.last_discovery_error = message
                    finally:
                        self.lock.release()
                self.stop_discovery.wait(10)

        self.discovery_thread = threading.Thread(target=monitor, name="esp32-discovery", daemon=True)
        self.discovery_thread.start()

    def close(self):
        self.stop_discovery.set()
        if self.discovery_thread:
            self.discovery_thread.join(timeout=20)

    def predict(self, pixels, threshold, model_sha256, request_id, slot_id):
        from backend.service.esp32_discovery import discover_device, DiscoveryError
        with self.lock:
            for attempt in range(2 if self.auto else 1):
                try:
                    if self.auto and (not self.base_url or time.monotonic() - self.discovered_at > 60):
                        from backend.service.esp32_discovery import check_device
                        if not self.base_url or not check_device(self.base_url, model_sha256):
                            self.base_url = None
                            self.base_url = discover_device(model_sha256)
                        self.discovered_at = time.monotonic()
                        self.last_discovery_error = None
                        logging.getLogger("uvicorn.error").info("ESP32 discovered: %s", self.base_url)
                    return self._predict(pixels, threshold, model_sha256, request_id, slot_id)
                except DiscoveryError as error:
                    self.base_url = None
                    raise DeviceError(str(error)) from error
                except DeviceError:
                    if not self.auto:
                        raise
                    self.base_url = None
                    if attempt:
                        raise

    def _predict(self, pixels, threshold, model_sha256, request_id, slot_id):
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
