"""Compose the gateway endpoint routers."""
from fastapi import APIRouter
from backend.api.endpoints import camera, prediction, status

router = APIRouter()
router.include_router(status.router)
router.include_router(prediction.router)
router.include_router(camera.router)
