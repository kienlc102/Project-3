"""Integration tests with real local weights and a simulated ESP32 HTTP node.

Run: python -m unittest discover -s tests -v
The simulated node verifies transport, NOT firmware execution on hardware.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app import create_app
from backend.roi import CameraConfig


class DeviceHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()
        self.wfile.write(self.server.frame)

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.received.append((dict(self.headers), data))
        if len(data) != 4096:
            self.send_error(400)
            return
        score = 0.9 if sum(data) / len(data) > 127 else 0.1
        threshold = float(self.headers["X-Threshold"])
        result = {"car_score": score, "label": int(score >= threshold), "threshold": threshold,
                  "latency_ms": 3.25, "request_id": self.headers["X-Request-Id"],
                  "slot_id": self.headers["X-Slot-Id"], "model_sha256": self.headers["X-Model-Sha256"]}
        if self.server.bad_identity:
            result["model_sha256"] = "0" * 64
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())


class GatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_dir = Path("ai_model/output/run_gpu01")
        if not (cls.model_dir / "parking_cnn_int8.tflite").is_file():
            raise unittest.SkipTest("Train run_gpu01 before running weight-dependent integration tests")
        image = Image.new("L", (128, 64), 0)
        image.paste(255, (64, 0, 128, 64))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        cls.frame = buffer.getvalue()
        cls.device = ThreadingHTTPServer(("127.0.0.1", 0), DeviceHandler)
        cls.device.frame, cls.device.received, cls.device.bad_identity = cls.frame, [], False
        cls.thread = threading.Thread(target=cls.device.serve_forever, daemon=True)
        cls.thread.start()
        base = f"http://127.0.0.1:{cls.device.server_port}"
        config = CameraConfig.model_validate({"camera_id": "camera_01", "reference_width": 128,
            "reference_height": 64, "snapshot_url": base + "/snapshot", "slots": [
                {"id": "left", "x": 0, "y": 0, "width": 64, "height": 64},
                {"id": "right", "x": 64, "y": 0, "width": 64, "height": 64}]})
        cls.config_patch = patch("backend.app.load_config", return_value=config)
        cls.config_patch.start()
        cls.client = TestClient(create_app(cls.model_dir, threshold=0.6, esp32_url=base, enable_reference=True))
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.config_patch.stop()
        cls.device.shutdown()
        cls.device.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.device.bad_identity = False
        self.device.received.clear()

    def upload(self, route, data=None):
        return self.client.post(route, files={"file": ("frame.png", self.frame if data is None else data, "image/png")})

    def test_roi_transport_and_snapshot(self):
        for route in ("/api/predict-frame?target=esp32", "/api/predict-camera?target=esp32"):
            response = self.upload(route) if "frame" in route else self.client.post(route)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertTrue(body["complete"])
            self.assertEqual(body["counts"], {"vacant": 1, "occupied": 1, "unknown": 0})
            self.assertEqual([item["slot_id"] for item in body["results"]], ["left", "right"])
            self.assertTrue(all(item["execution_target"] == "esp32" for item in body["results"]))
        self.assertEqual(len(self.device.received), 4)
        self.assertEqual(self.device.received[0][1], bytes(4096))
        self.assertEqual(self.device.received[1][1], bytes([255]) * 4096)

    def test_wrong_model_never_becomes_vacant(self):
        self.device.bad_identity = True
        response = self.upload("/api/predict-frame?target=esp32")
        body = response.json()
        self.assertFalse(body["complete"])
        self.assertEqual(body["counts"], {"vacant": 0, "occupied": 0, "unknown": 2})
        self.assertTrue(all(item["label"] is None for item in body["results"]))
        self.assertEqual(len(self.device.received), 1, "Stop dispatching after a device failure")
        self.assertEqual(self.upload("/api/predict?target=esp32").status_code, 502)

    def test_backend_reference_and_invalid_targets(self):
        for model in ("int8", "float"):
            response = self.upload(f"/api/predict?target=backend&model={model}")
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["execution_target"], "backend")
            self.assertEqual(body["label"], int(body["car_score"] >= 0.6))
        self.assertEqual(self.upload("/api/predict?target=esp32&model=float").status_code, 400)
        self.assertEqual(self.upload("/api/predict?target=invalid").status_code, 422)
        with patch.object(self.client.app.state.predictor, "device", None):
            self.assertEqual(self.upload("/api/predict").status_code, 503)

    def test_files_and_config_boundaries(self):
        self.assertEqual(self.upload("/api/predict?target=backend", b"bad image").status_code, 422)
        self.assertEqual(self.upload("/api/predict?target=backend", b"").status_code, 422)
        self.assertEqual(self.upload("/api/predict?target=backend", b"x" * (10 * 1024 * 1024 + 1)).status_code, 413)
        self.assertEqual(self.client.get("/ai_model/output/run_gpu01/parking_cnn.keras").status_code, 404)
        self.assertNotIn("snapshot_url", self.client.get("/api/rois").json()["camera"])
        image = Image.new("L", (64, 64))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        self.assertEqual(self.upload("/api/predict-frame?target=backend", buffer.getvalue()).status_code, 422)
        with patch.object(self.client.app.state, "camera", None):
            self.assertEqual(self.upload("/api/predict-frame?target=backend").status_code, 409)

    def test_roi_validation(self):
        with self.assertRaises(ValueError):
            CameraConfig.model_validate({"camera_id": "cam", "reference_width": 100, "reference_height": 100,
                "slots": [{"id": "a", "x": 99, "y": 0, "width": 2, "height": 10}]})

    def test_esp32_only_rejects_backend_reference(self):
        base = f"http://127.0.0.1:{self.device.server_port}"
        with TestClient(create_app(self.model_dir, esp32_url=base)) as client:
            self.assertEqual(client.get("/api/status").json()["execution_targets"], ["esp32"])
            response = client.post("/api/predict?target=backend", files={"file": ("frame.png", self.frame)})
            self.assertEqual(response.status_code, 503)
            response = client.post("/api/predict-frame", files={"file": ("frame.png", self.frame)})
            self.assertTrue(response.json()["complete"])


if __name__ == "__main__":
    unittest.main()
