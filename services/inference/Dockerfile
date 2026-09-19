FROM cgr.dev/chainguard/wolfi-base@sha256:1d95114038f76513a9ace6fca107d5582b08c65981f81f61cb56bf7fd2ef216d AS builder

RUN apk add --no-cache \
        py3.12-pip \
        python-3.12
WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN python3.12 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir '.[landmarks]'

FROM cgr.dev/chainguard/wolfi-base@sha256:1d95114038f76513a9ace6fca107d5582b08c65981f81f61cb56bf7fd2ef216d AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    PATH=/opt/venv/bin:$PATH

RUN apk add --no-cache \
        glib \
        libgomp \
        libstdc++ \
        mesa-egl \
        mesa-gl \
        mesa-gles \
        python-3.12
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY models/hand_landmarker.task ./models/hand_landmarker.task
COPY models/nail-segmentation.onnx ./models/nail-segmentation.onnx
RUN test -s models/hand_landmarker.task && test -s models/nail-segmentation.onnx
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/opt/venv/bin/python"]
CMD ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--timeout-keep-alive", "15", "--no-access-log"]
