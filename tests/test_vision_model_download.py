"""Integrity and preservation checks for the pinned parking car weights."""
from contextlib import redirect_stdout
import hashlib
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ai_model.prepare_vision_model import prepare_parking_car
from backend.config.settings import PROJECT_ROOT
from backend.config.vision import PARKING_CAR_FILENAME


class ParkingModelDownloadTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(dir=PROJECT_ROOT, prefix=".tmp-parkly-model-")
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name)
        self.payload = b"test weight content"
        self.digest = hashlib.sha256(self.payload).hexdigest()

    def test_only_verified_bytes_become_model_file(self):
        with patch("ai_model.prepare_vision_model.PARKING_CAR_SHA256", self.digest), \
             patch("ai_model.prepare_vision_model.urlopen", return_value=BytesIO(self.payload)), \
             redirect_stdout(StringIO()):
            destination = prepare_parking_car(self.output)
        self.assertEqual(destination.read_bytes(), self.payload)
        self.assertFalse(destination.with_suffix(".pt.part").exists())

    def test_corrupt_download_is_not_published(self):
        with patch("ai_model.prepare_vision_model.PARKING_CAR_SHA256", self.digest), \
             patch("ai_model.prepare_vision_model.urlopen", return_value=BytesIO(b"corrupt")):
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                prepare_parking_car(self.output)
        self.assertFalse((self.output / PARKING_CAR_FILENAME).exists())
        self.assertFalse(list(self.output.glob("*.part")))

    def test_existing_custom_file_is_preserved_and_valid_file_reused(self):
        destination = self.output / PARKING_CAR_FILENAME
        destination.write_bytes(b"custom weights")
        with patch("ai_model.prepare_vision_model.PARKING_CAR_SHA256", self.digest), \
             patch("ai_model.prepare_vision_model.urlopen") as download:
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                prepare_parking_car(self.output)
            self.assertEqual(destination.read_bytes(), b"custom weights")
            destination.write_bytes(self.payload)
            with redirect_stdout(StringIO()):
                self.assertEqual(prepare_parking_car(self.output), destination)
            download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
