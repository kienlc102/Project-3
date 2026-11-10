"""Camera-only API and detector contract tests; no pretrained weights/hardware required."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import HTTPException
import numpy as np
from PIL import Image

from backend.app import create_app
from backend.model.vision import VisionPredictor
from backend.model.inference import read_frame
from backend.schemas.camera import CameraConfig
from backend.service.camera_capture import capture_local
from backend.config.vision import DEFAULT_VISION_MODEL


class Array:
    def __init__(self, values):
        self.values = values

    def cpu(self):
        return self

    def tolist(self):
        return self.values


def detection_output(boxes=(), scores=(), classes=(), names=None):
    return SimpleNamespace(boxes=SimpleNamespace(xyxy=Array(list(boxes)), conf=Array(list(scores)),
                                                 cls=Array(list(classes))),
                           names=names if names is not None else {0: "person", 1: "car", 2: "motorcycle"})


def camera_config(**source):
    return CameraConfig.model_validate({"camera_id": "pi_test", "reference_width": 200,
        "reference_height": 100, "slots": [
            {"id": "A", "x": 0, "y": 0, "width": 100, "height": 100},
            {"id": "B", "x": 100, "y": 0, "width": 100, "height": 100}], **source})


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.yolo = MagicMock()
        self.yolo.return_value.predict.return_value = [detection_output()]
        self.module_patch = patch.dict("sys.modules", {"ultralytics": SimpleNamespace(YOLO=self.yolo)})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        # Only file existence is checked before the fake YOLO loader; no weight fixture is needed.
        self.model_path = Path(__file__).resolve()
        self.config_patch = patch("backend.app.load_config", return_value=camera_config())
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.cnn_patch = patch("backend.app.ParkingPredictor", side_effect=AssertionError("CNN must not load in vision-only mode"))
        self.cnn_patch.start()
        self.addCleanup(self.cnn_patch.stop)
        # Isolate the existing single-view API contract from the rotation-voting tests.
        self.client = TestClient(create_app(vision_model=self.model_path, vision_rotations=(0,), vision_edge_margin=0))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        buffer = BytesIO()
        Image.new("RGB", (200, 100), "white").save(buffer, format="PNG")
        self.frame = buffer.getvalue()

    def upload(self, data=None, query="target=raspberry_pi"):
        return self.client.post(f"/api/predict-frame?{query}",
                                files={"file": ("parking.png", self.frame if data is None else data, "image/png")})

    def test_vision_only_starts_without_cnn_and_exposes_status(self):
        health = self.client.get("/health").json()
        self.assertTrue(health["gateway_ready"])
        self.assertFalse(health["esp32_configured"])
        status = self.client.get("/api/status").json()
        self.assertEqual(status["execution_targets"], ["raspberry_pi"])
        self.assertEqual(status["default_target"], "raspberry_pi")
        self.assertEqual(status["models"], ["yolo"])
        self.assertEqual(status["vision"]["model"], self.model_path.name)
        self.assertEqual(self.upload(query="target=esp32").status_code, 503)
        self.assertEqual(self.upload(query="target=backend").status_code, 503)
        self.assertEqual(self.client.post("/api/predict?target=backend",
            files={"file": ("x.png", self.frame)}).status_code, 503)

    def test_full_rgb_frame_runs_once_and_maps_vehicle_classes(self):
        # COCO IDs are deliberately changed; labels, not IDs, define the vehicle classes.
        self.yolo.return_value.predict.return_value = [detection_output(
            [[10, 10, 90, 90], [110, 0, 200, 100]], [0.9, 0.99], [1, 0])]
        response = self.upload()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["counts"], {"occupied": 1, "vacant": 1, "unknown": 0})
        self.assertEqual(body["results"][0]["slot_coverage"], 0.64)
        self.assertEqual(len(body["detections"]), 1, "People must not occupy vehicle slots")
        self.assertEqual(body["latency_scope"], "full_frame")
        self.yolo.return_value.predict.assert_called_once()
        source = self.yolo.return_value.predict.call_args.kwargs["source"]
        self.assertEqual((source.mode, source.size), ("RGB", (200, 100)))

    def test_empty_frame_and_marginal_overlap(self):
        body = self.upload().json()
        self.assertEqual(body["counts"], {"occupied": 0, "vacant": 2, "unknown": 0})
        self.yolo.return_value.predict.return_value = [detection_output([[0, 0, 20, 100]], [0.95], [1])]
        body = self.upload(query="target=raspberry_pi&model=yolo").json()
        self.assertEqual(body["counts"], {"occupied": 0, "vacant": 1, "unknown": 1})
        self.assertIsNone(body["results"][0]["label"])
        self.assertFalse(body["complete"])

    def test_yolo_detection_api_does_not_require_rois(self):
        self.yolo.return_value.predict.return_value = [detection_output(
            [[10, 10, 90, 90], [110, 0, 200, 100]], [0.9, 0.99], [1, 0])]
        with patch.object(self.client.app.state, "camera", None):
            response = self.client.post("/api/detect/yolo", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["model"], "yolo")
        self.assertTrue(body["detected"])
        self.assertEqual(body["vehicle_count"], 1)
        self.assertEqual(body["detections"][0]["class_name"], "car")
        self.assertEqual(body["detections"][0]["box"], [10, 10, 90, 90])
        self.assertEqual(body["original_size"], [200, 100])
        self.assertNotIn("counts", body, "Object detection must not claim per-slot occupancy without ROIs")
        self.yolo.return_value.predict.assert_called_once()

    def test_yolo_empty_detection_and_failure_are_distinct(self):
        response = self.client.post("/api/detect/yolo", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["detected"])
        self.assertEqual(response.json()["vehicle_count"], 0)
        self.assertEqual(response.json()["detections"], [])
        self.yolo.return_value.predict.side_effect = RuntimeError("model failure")
        with self.assertLogs("uvicorn.error", level="ERROR"):
            response = self.client.post("/api/detect/yolo", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("detected", response.json())

    def test_yolo_debug_explains_vehicles_misclassified_as_phones(self):
        self.yolo.return_value.predict.return_value = [detection_output(
            [[10, 10, 80, 90], [110, 10, 190, 90]], [0.75, 0.70], [0, 0],
            names={0: "cell phone", 1: "car"})]
        response = self.client.post("/api/detect/yolo?debug=true", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertFalse(body["detected"])
        self.assertEqual(body["vehicle_count"], 0)
        self.assertEqual(body["diagnostics"]["reason"], "only_non_vehicle_detections")
        self.assertEqual([d["class_name"] for d in body["diagnostics"]["raw_detections"]], ["cell phone", "cell phone"])
        self.yolo.return_value.predict.assert_called_once()
        response = self.client.post("/api/detect/yolo", files={"file": ("frame.png", self.frame)})
        self.assertNotIn("diagnostics", response.json(), "Default responses must stay compatible")

    def test_yolo_debug_keeps_vehicle_filtering_and_empty_results(self):
        self.yolo.return_value.predict.return_value = [detection_output(
            [[10, 10, 80, 90], [110, 10, 190, 90]], [0.9, 0.99], [1, 0])]
        response = self.client.post("/api/detect/yolo?debug=true", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.json()["vehicle_count"], 1)
        self.assertEqual(response.json()["diagnostics"]["reason"], "vehicles_detected")
        self.assertEqual(len(response.json()["diagnostics"]["raw_detections"]), 2)
        self.yolo.return_value.predict.return_value = [detection_output()]
        response = self.client.post("/api/detect/yolo?debug=true", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.json()["diagnostics"]["reason"], "no_detections")
        self.assertEqual(response.json()["diagnostics"]["raw_detections"], [])

    def test_camera_counts_only_cars_with_case_insensitive_model_labels(self):
        self.yolo.return_value.predict.return_value = [detection_output(
            [[10, 10, 80, 90], [100, 10, 180, 90], [30, 20, 90, 80], [110, 20, 190, 80]],
            [0.9, 0.99, 0.95, 0.98], [0, 1, 2, 3],
            names={0: "Car", 1: "Bus", 2: "Truck", 3: "Motorcycle"})]
        response = self.client.post("/api/detect/yolo?debug=true", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["vehicle_count"], 1)
        self.assertEqual(body["detections"][0]["class_name"], "car")
        self.assertEqual(body["diagnostics"]["vehicle_classes"], ["car"])
        self.assertEqual(len(body["diagnostics"]["raw_detections"]), 4)
        body = self.upload().json()
        self.assertEqual(body["counts"], {"occupied": 1, "vacant": 1, "unknown": 0})

    def test_parking_car_profile_resolves_to_local_weights_without_download(self):
        with patch("backend.config.vision.DEFAULT_VISION_MODEL", self.model_path):
            predictor = VisionPredictor("parking-car")
        self.assertEqual(predictor.model_path, self.model_path)
        self.yolo.assert_called_with(str(self.model_path), task="detect")

    def test_detection_api_upload_validation_and_disabled_branches(self):
        for content, expected in [(b"bad", 422), (b"", 422), (b"x" * (10 * 1024 * 1024 + 1), 413)]:
            with self.subTest(expected=expected):
                response = self.client.post("/api/detect/yolo", files={"file": ("frame.png", content)})
                self.assertEqual(response.status_code, expected)
        self.assertEqual(self.client.post("/api/detect/yolo").status_code, 422)
        response = self.client.post("/api/detect/tinyml", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.status_code, 503, "TinyML must not silently execute YOLO")
        with patch.object(self.client.app.state, "vision", None):
            response = self.client.post("/api/detect/yolo", files={"file": ("frame.png", self.frame)})
            self.assertEqual(response.status_code, 503)

    def test_upload_decoder_ignores_optional_library_image_open_patch(self):
        with patch("PIL.Image.open", side_effect=AssertionError("Third-party decoder must not handle uploads")):
            self.assertEqual(read_frame(self.frame).size, (200, 100))
            with self.assertRaises(Image.UnidentifiedImageError):
                read_frame(b"invalid image")

    def test_separate_detection_apis_are_documented_in_openapi(self):
        schema = self.client.get("/openapi.json").json()
        tinyml = schema["paths"]["/api/detect/tinyml"]["post"]
        yolo = schema["paths"]["/api/detect/yolo"]["post"]
        self.assertEqual(next(p for p in tinyml["parameters"] if p["name"] == "target")["schema"]["default"], "backend")
        for endpoint in [tinyml, yolo]:
            self.assertIn("multipart/form-data", endpoint["requestBody"]["content"])
        self.assertIn("YoloDetectionResponse", schema["components"]["schemas"])

    def test_vision_and_esp32_can_be_enabled_together(self):
        with patch("backend.app.ParkingPredictor") as cnn:
            cnn.return_value.status.return_value = {
                "ready": True, "run": "tinyml", "models": ["int8"],
                "execution_targets": ["esp32"], "threshold": 0.75}
            with TestClient(create_app(esp32_url="http://esp32", vision_model=self.model_path)) as client:
                status = client.get("/api/status").json()
                self.assertEqual(status["execution_targets"], ["esp32", "raspberry_pi"])
                self.assertEqual(status["models"], ["int8", "yolo"])
                self.assertEqual(status["default_target"], "esp32")
                self.assertIn("vision", status)
                self.assertFalse(cnn.call_args.args[3], "TensorFlow reference mode must stay disabled")

    def test_model_errors_never_become_vacant(self):
        outputs = [RuntimeError("model failure"), detection_output(names={0: "person"}),
                   detection_output([[0, 0, 100, 100]], [float("nan")], [1])]
        for output in outputs:
            with self.subTest(output=type(output).__name__):
                if isinstance(output, Exception):
                    self.yolo.return_value.predict.side_effect = output
                else:
                    self.yolo.return_value.predict.side_effect = None
                    self.yolo.return_value.predict.return_value = [output]
                with self.assertLogs("uvicorn.error", level="ERROR"):
                    response = self.upload()
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["counts"], {"occupied": 0, "vacant": 0, "unknown": 2})

    def test_scaled_rois_and_aspect_ratio(self):
        buffer = BytesIO()
        Image.new("RGB", (400, 200)).save(buffer, format="PNG")
        self.yolo.return_value.predict.return_value = [detection_output([[0, 0, 200, 200]], [0.8], [1])]
        body = self.upload(buffer.getvalue()).json()
        self.assertEqual(body["results"][0]["box"], [0, 0, 200, 200])
        self.assertEqual(body["counts"]["occupied"], 1)
        buffer = BytesIO()
        Image.new("RGB", (100, 100)).save(buffer, format="PNG")
        self.assertEqual(self.upload(buffer.getvalue()).status_code, 422)

    def test_invalid_images_missing_roi_and_missing_vision(self):
        self.assertEqual(self.upload(b"bad").status_code, 422)
        self.assertEqual(self.upload(b"").status_code, 422)
        self.assertEqual(self.upload(b"x" * (10 * 1024 * 1024 + 1)).status_code, 413)
        with patch.object(self.client.app.state, "camera", None):
            self.assertEqual(self.upload().status_code, 409)
        with patch.object(self.client.app.state, "vision", None):
            self.assertEqual(self.upload().status_code, 503)

    def test_camera_capture_and_http_sources(self):
        with patch.object(self.client.app.state, "camera", camera_config(capture_device=0)), \
             patch("backend.api.endpoints.camera.capture_local", return_value=self.frame) as capture:
            response = self.client.post("/api/predict-camera?target=raspberry_pi")
            self.assertEqual(response.status_code, 200, response.text)
            capture.assert_called_once()
        with patch.object(self.client.app.state, "camera", camera_config(snapshot_url="http://camera/snapshot")), \
             patch("backend.api.endpoints.camera.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = self.frame
            response = self.client.post("/api/predict-camera?target=raspberry_pi")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("snapshot_url", self.client.get("/api/rois").json()["camera"])
            urlopen.side_effect = OSError("offline")
            self.assertEqual(self.client.post("/api/predict-camera?target=raspberry_pi").status_code, 502)
        self.assertEqual(self.client.post("/api/predict-camera?target=raspberry_pi").status_code, 409)

    def test_usb_driver_closes_on_success_and_failure(self):
        cv2 = MagicMock()
        capture = cv2.VideoCapture.return_value
        capture.read.return_value = (True, np.zeros((100, 200, 3), dtype=np.uint8))
        cv2.cvtColor.side_effect = lambda frame, _: frame
        with patch.dict("sys.modules", {"cv2": cv2}):
            data = capture_local(camera_config(capture_device=0))
            self.assertEqual(Image.open(BytesIO(data)).size, (200, 100))
            capture.release.assert_called_once()
            capture.release.reset_mock()
            capture.read.side_effect = OSError("USB disconnected")
            with self.assertLogs("uvicorn.error", level="ERROR"), self.assertRaises(HTTPException) as error:
                capture_local(camera_config(capture_device=0))
            self.assertEqual(error.exception.status_code, 502)
            capture.release.assert_called_once()

    def test_csi_rgb_conversion_and_missing_driver(self):
        picamera2 = MagicMock()
        capture = picamera2.Picamera2.return_value.__enter__.return_value
        bgr = np.zeros((100, 200, 3), dtype=np.uint8)
        bgr[..., 2] = 255
        capture.capture_array.return_value = bgr
        with patch.dict("sys.modules", {"picamera2": picamera2}), patch("backend.service.camera_capture.time.sleep"):
            data = capture_local(camera_config(use_picamera2=True))
            pixel = Image.open(BytesIO(data)).getpixel((50, 50))
            self.assertGreater(pixel[0], 240, "Picamera2 BGR arrays must become RGB images")
            self.assertLess(pixel[2], 10)
            picamera2.Picamera2.return_value.__exit__.assert_called_once()
        with patch.dict("sys.modules", {"picamera2": None}):
            with self.assertRaises(HTTPException) as error:
                capture_local(camera_config(use_picamera2=True))
            self.assertEqual(error.exception.status_code, 503)

    def test_config_and_threshold_validation(self):
        with self.assertRaises(ValueError):
            camera_config(capture_device=0, use_picamera2=True)
        for options in ({"confidence": float("nan")}, {"confidence": 0}, {"overlap": 1.1},
                        {"overlap": 0}, {"image_size": 33}, {"rotations": ()},
                        {"rotations": (0, 0)}, {"rotations": (45,)},
                        {"edge_margin": -1}, {"edge_margin": float("nan")}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                VisionPredictor(self.model_path, **options)
        with self.assertRaises(FileNotFoundError):
            VisionPredictor("missing-vision-model.pt")

    def test_rotation_voting_recovers_a_car_without_relabeling_trucks(self):
        self.client.app.state.vision = VisionPredictor(self.model_path)
        names = {0: "car", 1: "truck", 2: "motorcycle"}
        self.yolo.return_value.predict.side_effect = [
            [detection_output([[10, 20, 40, 70]], [0.69], [1], names)],
            [detection_output([[20, 160, 70, 190]], [0.51], [0], names)],
            [detection_output(names=names)],
            [detection_output([[30, 10, 80, 40]], [0.86], [0], names)],
        ]
        response = self.client.post("/api/detect/yolo?debug=true", files={"file": ("frame.png", self.frame)})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["vehicle_count"], 1)
        self.assertEqual(body["confidence_threshold"], 0.75)
        detection = body["detections"][0]
        self.assertEqual(detection["class_name"], "car")
        self.assertEqual(detection["support_views"], 2)
        self.assertAlmostEqual(detection["confidence"], 0.86)
        for actual, expected in zip(detection["box"], [10, 20, 40, 70]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual([d["class_name"] for d in body["diagnostics"]["view_detections"]], ["truck", "car", "car"])
        calls = self.yolo.return_value.predict.call_args_list
        self.assertEqual([c.kwargs["source"].size for c in calls], [(200, 100), (100, 200), (200, 100), (100, 200)])
        self.assertTrue(all(c.kwargs["conf"] == 0.35 for c in calls))

    def test_truncated_image_count_does_not_change_roi_occupancy(self):
        self.client.app.state.vision = VisionPredictor(self.model_path, rotations=(0,), edge_margin=1)
        self.yolo.return_value.predict.return_value = [detection_output([[0, 0, 80, 90]], [0.9], [1])]
        response = self.client.post("/api/detect/yolo?debug=true", files={"file": ("frame.png", self.frame)})
        body = response.json()
        self.assertEqual(body["vehicle_count"], 0)
        self.assertEqual(body["diagnostics"]["reason"], "vehicles_filtered")
        self.assertEqual(body["diagnostics"]["rejected_detections"][0]["reason"], "truncated_at_border")
        self.assertEqual(self.upload().json()["counts"], {"occupied": 1, "vacant": 1, "unknown": 0})


class ParkingCarWeightsTests(unittest.TestCase):
    """Regression for the actual overhead camera model when local weights/images exist."""

    def test_mixed_vehicle_scenes_at_both_thresholds(self):
        import importlib.util
        expected = {"test1.jpg": 5, "test2.jpg": 2, "shadow-only-shadow.jpg": 0,
                    "test2-nocar.jpg": 0, "empty-parking-lot-michigan.jpg": 0}
        if (not DEFAULT_VISION_MODEL.is_file() or not importlib.util.find_spec("ultralytics")
                or any(not (Path("test_image") / name).is_file() for name in expected)):
            self.skipTest("Prepare local parking-car weights and test images")
        for confidence in (0.35, 0.75):
            with TestClient(create_app(vision_model="parking-car", vision_confidence=confidence)) as client:
                for name, count in expected.items():
                    with self.subTest(image=name, confidence=confidence):
                        response = client.post("/api/detect/yolo?debug=true", files={
                            "file": (name, (Path("test_image") / name).read_bytes(), "image/jpeg")})
                        self.assertEqual(response.status_code, 200, response.text)
                        body = response.json()
                        self.assertEqual(body["confidence_threshold"], confidence)
                        self.assertEqual(body["vehicle_count"], count)
                        self.assertTrue(all(d["class_name"] == "car" and d["confidence"] >= confidence
                                            and d["support_views"] >= 2 for d in body["detections"]))
                        if name == "test1.jpg":
                            self.assertTrue(any(d["class_name"] == "motorcycle" for d in body["diagnostics"]["raw_detections"]))

    def test_shadow_cars_are_detected_by_new_profile(self):
        import importlib.util
        image_path = Path("test_image/shadow-only-car.jpg")
        if not DEFAULT_VISION_MODEL.is_file() or not image_path.is_file() or not importlib.util.find_spec("ultralytics"):
            self.skipTest("Prepare parking-car weights and the local test image to run this regression")
        with TestClient(create_app(vision_model="parking-car")) as client:
            response = client.post("/api/detect/yolo", files={"file": (image_path.name, image_path.read_bytes(), "image/jpeg")})
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["vehicle_count"], 2)
            self.assertTrue(all(d["class_name"] == "car" and d["confidence"] > 0.8 for d in body["detections"]))
            self.assertEqual(client.get("/api/status").json()["vision"]["profile"], "parking-car")
            self.assertEqual(client.get("/api/status").json()["vision"]["vehicle_classes"], ["car"])
            camera = CameraConfig(camera_id="regression", reference_width=359, reference_height=240,
                slots=[{"id": "left", "x": 40, "y": 10, "width": 120, "height": 230},
                       {"id": "right", "x": 180, "y": 10, "width": 120, "height": 230}])
            with patch.object(client.app.state, "camera", camera):
                response = client.post("/api/predict-frame?target=raspberry_pi",
                    files={"file": (image_path.name, image_path.read_bytes(), "image/jpeg")})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["counts"], {"occupied": 2, "vacant": 0, "unknown": 0})


if __name__ == "__main__":
    unittest.main()
