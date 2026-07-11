from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CaptureType(StrEnum):
    LEFT_FINGERS = "left_fingers"
    LEFT_THUMB = "left_thumb"
    RIGHT_FINGERS = "right_fingers"
    RIGHT_THUMB = "right_thumb"


class QualityIssueCode(StrEnum):
    REFERENCE_MISSING = "REFERENCE_MISSING"
    REFERENCE_INVALID = "REFERENCE_INVALID"
    BLUR = "BLUR"
    GLARE = "GLARE"
    ANGLE_TOO_STEEP = "ANGLE_TOO_STEEP"
    NAIL_CROPPED = "NAIL_CROPPED"
    NAIL_OCCLUDED = "NAIL_OCCLUDED"
    WRONG_NAIL_COUNT = "WRONG_NAIL_COUNT"
    UNSUPPORTED_NAIL_CONDITION = "UNSUPPORTED_NAIL_CONDITION"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    OUTSIDE_DEFAULT_CHART = "OUTSIDE_DEFAULT_CHART"


class QualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: QualityIssueCode
    message: str
    correction: str


class NailMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digit: Literal["thumb", "index", "middle", "ring", "pinky"]
    projected_width_mm: float = Field(gt=0)
    uncertainty_mm: float = Field(ge=0)
    recommended_size: str
    alternate_size: str | None
    confidence: Literal["high", "medium", "low"]
    contour: list[tuple[float, float]]


class MeasureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "retake"]
    request_id: str
    capture_type: CaptureType
    measurements: list[NailMeasurement]
    quality_issues: list[QualityIssue]
    model_version: str
    chart_id: Literal["platform-default"] = "platform-default"
    chart_version: Literal["1"] = "1"
    processing_ms: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: Literal["ok", "not_ready"]
    model_version: str
