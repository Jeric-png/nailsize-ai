FROM cgr.dev/chainguard/wolfi-base@sha256:02dab76bd852a70556b5b2002195c8a5fdab77d323c433bf6642aab080489795 AS builder

RUN apk add --no-cache \
        py3.12-pip \
        python-3.12
WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN python3.12 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir '.[landmarks]'

FROM cgr.dev/chainguard/wolfi-base@sha256:02dab76bd852a70556b5b2002195c8a5fdab77d323c433bf6642aab080489795 AS runtime

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
