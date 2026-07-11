import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://example.com/measure",
        "https://example.com/",
        "https://user@example.com",
        "https://example.com?preview=true",
        "javascript://example.com",
        "http://example.com",
    ],
)
def test_development_rejects_non_exact_or_unsafe_origins(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(allowed_origins=origin)


def test_development_accepts_loopback_http_and_exact_https_origins() -> None:
    settings = Settings(
        allowed_origins="http://localhost:5173,http://127.0.0.1:4173,https://preview.example.com"
    )

    assert settings.origins == [
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "https://preview.example.com",
    ]


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_non_development_environments_require_https(environment: str) -> None:
    with pytest.raises(ValidationError):
        Settings(
            deployment_environment=environment,
            allowed_origins="http://localhost:5173",
        )


def test_production_accepts_multiple_exact_https_origins() -> None:
    settings = Settings(
        deployment_environment="production",
        allowed_origins="https://nails.example.com,https://www.nails.example.com",
    )

    assert settings.origins == [
        "https://nails.example.com",
        "https://www.nails.example.com",
    ]


def test_origins_cannot_be_empty_or_duplicated() -> None:
    with pytest.raises(ValidationError):
        Settings(allowed_origins=" , ")
    with pytest.raises(ValidationError):
        Settings(allowed_origins="https://example.com,https://example.com")


def test_configured_model_requires_validated_boundary_error() -> None:
    with pytest.raises(ValidationError, match="SEGMENTATION_BOUNDARY_ERROR_PX"):
        Settings(model_sha256="0" * 64)
    with pytest.raises(ValidationError, match="must be positive"):
        Settings(segmentation_boundary_error_px=0)

    settings = Settings(model_sha256="0" * 64, segmentation_boundary_error_px=0.5)
    assert settings.segmentation_boundary_error_px == 0.5
