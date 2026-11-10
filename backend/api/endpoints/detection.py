"""Separate upload APIs for testing TinyML classification and YOLO detection."""
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from PIL import Image

from backend.api.endpoints.prediction import predict
from backend.api.uploads import read_upload
from backend.model.inference import read_frame
from backend.schemas.detection import YoloDetectionResponse
from backend.schemas.prediction import PredictionResponse

router = APIRouter(prefix="/api/detect", tags=["Car detection"])


@router.post("/tinyml", response_model=PredictionResponse,
             summary="TinyML CNN: kiểm tra ảnh một ô đỗ",
             description="Upload ảnh đã crop một ô. Mặc định chạy CNN trên backend, không cần ESP32 hay ROI. "
                         "Chọn target=esp32 để gửi ảnh tới thiết bị đã cấu hình. Chỉ trả kết quả CNN, chưa có sensor fusion.")
def detect_tinyml(
    request: Request,
    file: Annotated[UploadFile, File(description="Ảnh một ô đỗ; JPG/PNG/WebP/BMP, tối đa 10 MB")],
    model: Annotated[Literal["int8", "float"], Query(description="Định dạng model TinyML")] = "int8",
    target: Annotated[Literal["backend", "esp32"], Query(description="Nơi chạy CNN")] = "backend",
):
    return predict(request, file, model, target)


@router.post("/yolo", response_model=YoloDetectionResponse, response_model_exclude_none=True,
             summary="Camera: phát hiện ô tô và trả bounding box trên toàn ảnh",
             description="Không cần ROI, ESP32 hoặc camera thật. Dùng model đã bật bằng --vision-model; "
                         "Profile parking-car dùng Geo-trax cho góc nhìn từ trên cao; chỉ trả lớp car, không suy ra trạng thái từng ô.")
def detect_yolo(
    request: Request,
    file: Annotated[UploadFile, File(description="Ảnh toàn cảnh; JPG/PNG/WebP/BMP, tối đa 10 MB")],
    debug: Annotated[bool, Query(description="Hiển thị các nhãn model trả về trước khi lọc lớp xe; không chạy model thêm lần nữa")] = False,
):
    data = read_upload(file)
    vision = request.app.state.vision
    if vision is None:
        raise HTTPException(503, "YOLO chưa bật. Khởi động với --vision-model.")
    try:
        image = read_frame(data)
    except (ValueError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise HTTPException(422, "Ảnh không hợp lệ, không được hỗ trợ hoặc quá lớn.") from error
    try:
        return vision.predict_image(image, debug=debug)
    except Exception as error:
        logging.getLogger("uvicorn.error").exception("YOLO detection failed")
        raise HTTPException(500, "Không thể chạy YOLO. Xem terminal backend.") from error
