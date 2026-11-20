import json
import os
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

from backend.service.host_network import detect_host_subnets, normalize_interfaces, discovery_subnets


class HostNetworkTests(unittest.TestCase):
    def test_real_masks_used_instead_of_assuming_24(self):
        self.assertEqual(normalize_interfaces([
            {"address": "192.168.10.53", "netmask": "255.255.254.0"},
            {"address": "10.2.3.99", "netmask": "24"},
            {"address": "127.0.0.1", "netmask": "8"},
            {"address": "169.254.1.2", "netmask": "16"},
        ]), ["10.2.3.0/24", "192.168.10.0/23"])

    def test_metadata_reread_after_host_changes_wifi(self):
        with patch.dict(os.environ, {"ESP32_HOST_NETWORK_FILE": "host-network.json"}):
            with patch.object(Path, "stat", return_value=SimpleNamespace(st_mtime=time.time())):
                for address, expected in [("192.168.1.12", "192.168.1.0/24"), ("10.5.0.19", "10.5.0.0/24")]:
                    payload = json.dumps({"interfaces": [{"address": address, "netmask": "24"}]})
                    with patch.object(Path, "read_text", return_value=payload):
                        self.assertEqual(detect_host_subnets(), [expected])

    def test_stale_metadata_does_not_scan_previous_location(self):
        with patch.dict(os.environ, {"ESP32_HOST_NETWORK_FILE": "host-network.json"}):
            with patch.object(Path, "stat", return_value=SimpleNamespace(st_mtime=time.time() - 100)):
                with self.assertRaisesRegex(ValueError, "stale"):
                    detect_host_subnets()

    def test_manual_override_is_optional(self):
        with patch.dict(os.environ, {"ESP32_DISCOVERY_SUBNETS": "10.0.1.0/24"}):
            with patch("backend.service.host_network.detect_host_subnets") as detect:
                self.assertEqual(discovery_subnets(), "10.0.1.0/24")
                detect.assert_not_called()

    def test_auto_detects_without_fixed_subnet(self):
        with patch.dict(os.environ, {"ESP32_DISCOVERY_SUBNETS": "auto"}):
            with patch("backend.service.host_network.detect_host_subnets", return_value=["172.20.10.0/28"]):
                self.assertEqual(discovery_subnets(), "172.20.10.0/28")


if __name__ == "__main__":
    unittest.main()
