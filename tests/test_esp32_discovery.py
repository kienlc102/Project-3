"""Discovery/transport tests; no LAN device or zeroconf installation required."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError

import numpy as np

from backend.service.esp32_client import Esp32Client, DeviceError
from backend.service.esp32_discovery import select_device, DiscoveryError, discover_device, scan_candidates

MODEL = "a" * 64


class NodeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(self.server.health).encode())

    def do_POST(self):
        pixels = self.rfile.read(int(self.headers["Content-Length"]))
        self.server.received.append(pixels)
        threshold = float(self.headers["X-Threshold"])
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({
            "request_id": self.headers["X-Request-Id"],
            "slot_id": self.headers["X-Slot-Id"],
            "model_sha256": MODEL, "car_score": 0.8,
            "label": int(0.8 >= threshold), "threshold": threshold,
            "latency_ms": 12.5,
        }).encode())


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.node = ThreadingHTTPServer(("127.0.0.1", 0), NodeHandler)
        self.node.health = {"device_type": "parkly-esp32", "ready": True,
                            "model_sha256": MODEL, "input_bytes": 4096}
        self.node.received = []
        self.thread = threading.Thread(target=self.node.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.node.server_port}"

    def tearDown(self):
        self.node.shutdown()
        self.node.server_close()
        self.thread.join()

    def test_health_verified_and_candidates_deduplicated(self):
        self.assertEqual(select_device([self.url, self.url], MODEL), self.url)

    def test_wrong_model_rejected(self):
        with self.assertRaises(DiscoveryError):
            select_device([self.url], "b" * 64)

    def test_not_ready_rejected(self):
        self.node.health["ready"] = False
        with self.assertRaises(DiscoveryError):
            select_device([self.url], MODEL)

    def test_other_http_service_rejected(self):
        self.node.health["device_type"] = "other"
        with self.assertRaises(DiscoveryError):
            select_device([self.url], MODEL)

    def test_multiple_boards_rejected(self):
        second = self.url.replace("127.0.0.1", "127.0.0.2")
        class Reply:
            def __enter__(inner): return inner
            def __exit__(inner, *args): pass
            def read(inner, size): return json.dumps(self.node.health).encode()
        with patch("backend.service.esp32_discovery.urlopen", return_value=Reply()):
            with self.assertRaises(DiscoveryError):
                select_device([self.url, second], MODEL)

    def test_auto_discovery_cached_between_predictions(self):
        client = Esp32Client("auto")
        pixels = np.zeros((64, 64, 1), dtype=np.uint8)
        with patch("backend.service.esp32_discovery.discover_device", return_value=self.url) as discover:
            for index in range(2):
                result = client.predict(pixels, 0.6, MODEL, f"request_{index}", "slot_1")
                self.assertEqual(result["car_score"], 0.8)
            discover.assert_called_once_with(MODEL)
        self.assertEqual([len(data) for data in self.node.received], [4096, 4096])

    def test_rediscovery_after_changed_ip(self):
        client = Esp32Client("auto")
        pixels = np.zeros((64, 64, 1), dtype=np.uint8)
        with patch("backend.service.esp32_discovery.discover_device", side_effect=["http://old-ip", self.url]) as discover:
            with patch.object(client, "_predict", side_effect=[DeviceError("offline"), {"car_score": 0.8}]):
                result = client.predict(pixels, 0.6, MODEL, "req", "slot")
                self.assertEqual(result["car_score"], 0.8)
                self.assertEqual(discover.call_count, 2)
                self.assertEqual(client.base_url, self.url)

    def test_manual_url_never_discovers(self):
        with patch("backend.service.esp32_discovery.discover_device") as discover:
            Esp32Client(self.url).predict(np.zeros((64, 64, 1), dtype=np.uint8), 0.6, MODEL, "req", "slot")
            discover.assert_not_called()

    def test_missing_multicast_and_subnet_has_actionable_error(self):
        with patch.dict("os.environ", {"ESP32_DISCOVERY_SUBNETS": ""}):
            with patch("backend.service.esp32_discovery.discover_mdns", side_effect=DiscoveryError("offline")):
                with patch("backend.service.host_network.detect_host_subnets", return_value=[]):
                    with self.assertRaisesRegex(DiscoveryError, "host LAN"):
                        discover_device(MODEL)

    def test_subnet_fallback_without_any_host_service(self):
        with patch.dict("os.environ", {"ESP32_DISCOVERY_SUBNETS": "192.168.36.0/30"}):
            with patch("backend.service.esp32_discovery.discover_mdns", side_effect=DiscoveryError("blocked")):
                with patch("backend.service.esp32_discovery.check_device", side_effect=lambda url, *args, **kw: url == "http://192.168.36.2:80"):
                    self.assertEqual(discover_device(MODEL), "http://192.168.36.2:80")

    def test_subnet_scan_rejects_public_or_excessive_ranges(self):
        for subnet in ["0.0.0.0/0", "8.8.8.0/24", "192.168.0.0/16", "bad-value"]:
            with self.subTest(subnet=subnet), self.assertRaises(DiscoveryError):
                scan_candidates(subnet)

    def test_automatic_host_network_changes_are_used_on_rediscovery(self):
        with patch.dict("os.environ", {"ESP32_DISCOVERY_SUBNETS": "auto"}):
            with patch("backend.service.host_network.detect_host_subnets",
                       side_effect=[["192.168.1.0/30"], ["10.10.10.0/30"]]):
                with patch("backend.service.esp32_discovery.discover_mdns", side_effect=DiscoveryError("blocked")):
                    with patch("backend.service.esp32_discovery.check_device",
                               side_effect=lambda url, *args, **kw: url in ["http://192.168.1.2:80", "http://10.10.10.2:80"]):
                        self.assertEqual(discover_device(MODEL), "http://192.168.1.2:80")
                        self.assertEqual(discover_device(MODEL), "http://10.10.10.2:80")

    def test_background_discovery_starts_without_predict_request(self):
        client = Esp32Client("auto")
        discovered = threading.Event()
        def find(model):
            discovered.set()
            return self.url
        with patch("backend.service.esp32_discovery.discover_device", side_effect=find):
            client.start_discovery(MODEL)
            self.assertTrue(discovered.wait(2))
            client.close()
        self.assertEqual(client.base_url, self.url)
        self.assertFalse(client.discovery_thread.is_alive())

    def test_ambiguous_mdns_does_not_fall_back_to_another_board(self):
        from backend.service.esp32_discovery import MultipleDevicesError
        with patch("backend.service.esp32_discovery.discover_mdns", side_effect=MultipleDevicesError("ambiguous")):
            with patch("backend.service.esp32_discovery.scan_candidates") as scan:
                with self.assertRaises(MultipleDevicesError):
                    discover_device(MODEL)
                scan.assert_not_called()


if __name__ == "__main__":
    unittest.main()
