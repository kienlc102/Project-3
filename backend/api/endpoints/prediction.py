"""Single parking slot prediction endpoint."""
import logging
from typing import Annotated, Literal
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from backend.api.uploads import read_upload
from backend.schemas.prediction import PredictionResponse
from backend.service.esp32_client import DeviceError
from backend.service.prediction import validate_target

router = APIRouter()

@router.post("/api/predict", response_model=PredictionResponse, tags=["Prediction"],
              summary="Upload ảnh một ô đỗ và dự đoán có xe / không có xe",
              responses={413: {"description": "Ảnh vượt quá 10 MB"},
                         422: {"description": "Ảnh hoặc tham số không hợp lệ"}})
def predict(request: Request,
            file: Annotated[UploadFile, File(description="JPG, PNG, WebP or BMP; at most 10 MB")],
            model: Annotated[Literal["int8", "float"], Query(description="Model inference format")] = "int8",
            target: Annotated[Literal["esp32", "backend"], Query(description="ESP32 production path or backend reference test")] = "esp32"):
    predictor = request.app.state.predictor
    data = read_upload(file)
    validate_target(predictor, model, target)
    try:
        return predictor.predict(data, model, target)
    except DeviceError as error:
        raise HTTPException(502, str(error)) from error
    except (ValueError, OSError, predictor.Image.DecompressionBombError,
            predictor.Image.DecompressionBombWarning) as error:
        raise HTTPException(422, "Ảnh không hợp lệ, không được hỗ trợ hoặc quá lớn.") from error
    except Exception as error:
        logging.getLogger("uvicorn.error").exception("Inference failed")
        raise HTTPException(500, "Không thể chạy model. Xem terminal backend.") from error

