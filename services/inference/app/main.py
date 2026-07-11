import logging
import time
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .image_io import decode_upload
from .logging_config import safe_log
from .quality import assess_capture
from .schemas import CaptureType, HealthResponse, MeasureResponse, QualityIssue, QualityIssueCode

settings = get_settings()
logger = logging.getLogger("nailsize.inference")
app = FastAPI(title="NailSize Inference API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def privacy_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, error: Exception):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
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
    ready_state = settings.model_version != "unavailable"
    return JSONResponse(
        status_code=200 if ready_state else 503,
        content=HealthResponse(
            status="ok" if ready_state else "not_ready", model_version=settings.model_version
        ).model_dump(),
        headers={"Cache-Control": "no-store"},
    )


@app.post("/v1/measure", response_model=MeasureResponse)
async def measure(
    image: UploadFile = File(...),
    capture_type: CaptureType = Form(...),
    reference_type: str = Form(...),
) -> MeasureResponse:
    started = time.perf_counter()
    request_id = str(uuid4())
    decoded = await decode_upload(image, settings)
    try:
        issue: QualityIssue
        if reference_type != "iso_id1":
            issue = QualityIssue(
                code=QualityIssueCode.REFERENCE_INVALID,
                message="This reference type is not supported.",
                correction="Use a blank ISO ID-1 size card.",
            )
        else:
            capture_quality = assess_capture(decoded.rgb)
            if capture_quality.issues:
                issue = capture_quality.issues[0]
            else:
                issue = QualityIssue(
                    code=QualityIssueCode.LOW_CONFIDENCE,
                    message="Nail segmentation is not yet confident enough.",
                    correction=(
                        "Keep the nails separated, flat, and evenly lit, then retake the photo."
                    ),
                )
        elapsed = int((time.perf_counter() - started) * 1000)
        safe_log(
            logger,
            logging.INFO,
            event="measurement_retake",
            request_id=request_id,
            encoded_bytes=decoded.encoded_bytes,
            width_px=decoded.width,
            height_px=decoded.height,
            processing_ms=elapsed,
            model_version=settings.model_version,
            chart_version="1",
            status_code=200,
            error_code=issue.code.value,
        )
        return MeasureResponse(
            status="retake",
            request_id=request_id,
            capture_type=capture_type,
            measurements=[],
            quality_issues=[issue],
            model_version=settings.model_version,
            processing_ms=elapsed,
        )
    finally:
        decoded.close()
