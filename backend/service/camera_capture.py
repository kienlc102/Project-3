"""On-demand USB/CSI capture. Imports are optional for HTTP snapshot deployments."""
from io import BytesIO
import logging
import threading
import time

from fastapi import HTTPException
from PIL import Image

_capture_lock = threading.Lock()


def capture_local(camera):
    # Opening the same physical camera concurrently can fail or return stale frames.
    with _capture_lock:
        try:
            if camera.use_picamera2:
                from picamera2 import Picamera2
                with Picamera2() as capture:
                    capture.configure(capture.create_still_configuration(
                        main={"size": (camera.reference_width, camera.reference_height), "format": "RGB888"}))
                    capture.start()
                    time.sleep(1)  # Allow auto exposure to settle on a freshly opened camera.
                    # Picamera2 RGB888 arrays use BGR byte order.
                    image = Image.fromarray(capture.capture_array()[..., ::-1])
            else:
                import cv2
                capture = cv2.VideoCapture(camera.capture_device)
                try:
                    if not capture.isOpened():
                        raise OSError("Camera did not open")
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, camera.reference_width)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.reference_height)
                    for _ in range(3):
                        success, frame = capture.read()
                    if not success or frame is None:
                        raise OSError("Camera did not return a frame")
                    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                finally:
                    capture.release()
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=90)
            return buffer.getvalue()
        except ImportError as error:
            raise HTTPException(503, "Thiếu driver camera: cài OpenCV cho USB hoặc python3-picamera2 cho CSI.") from error
        except Exception as error:
            logging.getLogger("uvicorn.error").exception("Local camera capture failed")
            raise HTTPException(502, "Không đọc được camera cục bộ. Kiểm tra thiết bị và driver.") from error
