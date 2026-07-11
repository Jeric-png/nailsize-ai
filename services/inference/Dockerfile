FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib

RUN useradd --create-home --uid 10001 appuser
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libegl1 \
        libgl1 \
        libgles2 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install '.[landmarks]'
COPY models/hand_landmarker.task ./models/hand_landmarker.task
COPY models/nail-segmentation.onnx ./models/nail-segmentation.onnx
RUN test -s models/hand_landmarker.task && test -s models/nail-segmentation.onnx
USER appuser
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--timeout-keep-alive", "15", "--no-access-log"]
