FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app

COPY backend/requirements.txt backend/requirements-docker.txt ./backend/
RUN python -m pip install --no-cache-dir -r backend/requirements-docker.txt

COPY backend/ ./backend/
COPY ai_model/__init__.py ai_model/dataset_io.py ./ai_model/
COPY dashboard/ ./dashboard/

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "backend.app", "--host", "0.0.0.0", "--port", "8000"]
