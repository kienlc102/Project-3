FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app

# OpenCV (YOLO/USB capture) and the CPU inference runtimes need these libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements-vision.txt backend/requirements-docker.txt ./backend/
# Install CPU wheels first so Ultralytics does not pull CUDA dependencies.
RUN python -m pip install --no-cache-dir "torch>=2.6,<3" "torchvision>=0.21,<1" --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r backend/requirements-docker.txt \
    && python -m pip check

COPY backend/ ./backend/
COPY ai_model/__init__.py ai_model/dataset_io.py ./ai_model/
COPY dashboard/ ./dashboard/

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "backend.app", "--host", "0.0.0.0", "--port", "8000"]
