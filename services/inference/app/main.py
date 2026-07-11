import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .image_io import decode_upload
from .logging_config import safe_log
from .pipeline import run_measurement_pipeline
from .quality import assess_capture
from .request_limits import InMemoryRequestLimitMiddleware, configure_in_memory_multipart
from .runtime import RuntimeModels, load_runtime_models
from .schemas import CaptureType, HealthResponse, MeasureResponse, QualityIssue, QualityIssueCode

settings = get_settings()
max_request_body_bytes = configure_in_memory_multipart(settings.max_encoded_bytes)
logger = logging.getLogger("nailsize.inference")


@asynccontextmanager
async def lifespan(application: FastAPI):
    started = time.perf_counter()
    runtime = load_runtime_models(settings)
    application.state.runtime = runtime
    safe_log(
        logger,
        logging.INFO,
        event="runtime_initialized",
        duration_ms=int((time.perf_counter() - started) * 1000),
        cold_start=True,
        ready=runtime.ready,
        model_version=settings.model_version,
        chart_version="1",
        error_code=runtime.error_code,
    )
    try:
        yield
    finally:
        runtime.close()


app = FastAPI(title="NailSize Inference API", version="0.1.0", lifespan=lifespan)
app.state.runtime = RuntimeModels()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
)
app.add_middleware(
    InMemoryRequestLimitMiddleware,
    max_body_bytes=max_request_body_bytes,
)


@app.middleware("http")
async def privacy_headers(request: Request, call_next):
    started = time.perf_counter()
    request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Request-ID"] = request_id
    safe_log(
        logger,
        logging.INFO,
        event="request_completed",
        request_id=request_id,
        processing_ms=int((time.perf_counter() - started) * 1000),
        model_version=settings.model_version,
        chart_version="1",
        status_code=response.status_code,
    )
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, error: Exception):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    safe_log(
        logger,
        logging.ERROR,
        event="request_failed",
        request_id=request_id,
        status_code=500,
        error_code="INTERNAL_ERROR",
    )
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "request_id": request_id},
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", model_version=settings.model_version)


@app.get("/ready", response_model=HealthResponse, status_code=503)
async def ready() -> JSONResponse:
    ready_state = app.state.runtime.ready
    return JSONResponse(
        status_code=200 if ready_state else 503,
        content=HealthResponse(
            status="ok" if ready_state else "not_ready", model_version=settings.model_version
        ).model_dump(),
        headers={"Cache-Control": "no-store"},
    )


@app.post("/v1/measure", response_model=MeasureResponse)
async def measure(
    request: Request,
    image: UploadFile = File(...),
    capture_type: CaptureType = Form(...),
    reference_type: str = Form(...),
) -> MeasureResponse:
    started = time.perf_counter()
    request_id = request.state.request_id
    stage_started = time.perf_counter()
    decoded = await decode_upload(image, settings)
    safe_log(
        logger,
        logging.INFO,
        event="stage_completed",
        request_id=request_id,
        stage="upload_decode",
        duration_ms=int((time.perf_counter() - stage_started) * 1000),
        model_version=settings.model_version,
        chart_version="1",
    )
    try:
        issue: QualityIssue | None = None
        measurements = []
        if reference_type != "iso_id1":
            issue = QualityIssue(
                code=QualityIssueCode.REFERENCE_INVALID,
                message="This reference type is not supported.",
                correction="Use a blank ISO ID-1 size card.",
            )
        else:
            stage_started = time.perf_counter()
            capture_quality = assess_capture(decoded.rgb)
            safe_log(
                logger,
                logging.INFO,
                event="stage_completed",
                request_id=request_id,
                stage="capture_quality",
                duration_ms=int((time.perf_counter() - stage_started) * 1000),
                model_version=settings.model_version,
                chart_version="1",
            )
            if capture_quality.issues:
                issue = capture_quality.issues[0]
            else:
                runtime = app.state.runtime
                if (
                    not runtime.ready
                    or runtime.hand_detector is None
                    or runtime.segmentation is None
                    or settings.segmentation_boundary_error_px is None
                ):
                    issue = QualityIssue(
                        code=QualityIssueCode.LOW_CONFIDENCE,
                        message="The validated sizing model is not available.",
                        correction="Retry later; no measurement was returned from this photo.",
                    )
                else:
                    pipeline = run_measurement_pipeline(
                        decoded.rgb,
                        capture_type,
                        capture_quality.calibration,
                        runtime.hand_detector,
                        runtime.segmentation,
                        segmentation_boundary_error_px=settings.segmentation_boundary_error_px,
                    )
                    for stage, duration_ms in pipeline.stage_timings_ms.items():
                        safe_log(
                            logger,
                            logging.INFO,
                            event="stage_completed",
                            request_id=request_id,
                            stage=stage,
                            duration_ms=duration_ms,
                            model_version=settings.model_version,
                            chart_version="1",
                        )
                    issue = pipeline.issue
                    measurements = list(pipeline.measurements)
        elapsed = int((time.perf_counter() - started) * 1000)
        log_fields = dict(
            event="measurement_retake" if issue else "measurement_completed",
            request_id=request_id,
            encoded_bytes=decoded.encoded_bytes,
            width_px=decoded.width,
            height_px=decoded.height,
            processing_ms=elapsed,
            model_version=settings.model_version,
            chart_version="1",
            status_code=200,
        )
        if issue is not None:
            log_fields["error_code"] = issue.code.value
        elif measurements:
            confidence_order = {"low": 0, "medium": 1, "high": 2}
            log_fields["confidence_bucket"] = min(
                (item.confidence for item in measurements), key=confidence_order.get
            )
        safe_log(
            logger,
            logging.INFO,
            **log_fields,
        )
        return MeasureResponse(
            status="retake" if issue else "ok",
            request_id=request_id,
            capture_type=capture_type,
            measurements=measurements,
            quality_issues=[issue] if issue else [],
            model_version=settings.model_version,
            processing_ms=elapsed,
        )
    finally:
        decoded.close()
