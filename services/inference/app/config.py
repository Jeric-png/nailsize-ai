from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deployment_environment: Literal["development", "staging", "production"] = "development"
    allowed_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    hand_landmarker_path: str = "models/hand_landmarker.task"
    hand_landmarker_sha256: str = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"
    model_path: str = "models/nail-segmentation.onnx"
    model_sha256: str = ""
    model_version: str = "unavailable"
    max_encoded_bytes: int = 12 * 1024 * 1024
    max_decoded_pixels: int = 25_000_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_origins(self) -> "Settings":
        origins = self.origins
        if not origins:
            raise ValueError("ALLOWED_ORIGINS must contain at least one exact origin")

        for origin in origins:
            if origin == "*":
                raise ValueError("ALLOWED_ORIGINS cannot contain a wildcard")

            parsed = urlsplit(origin)
            try:
                _ = parsed.port
            except ValueError as error:
                raise ValueError(f"ALLOWED_ORIGINS contains an invalid port: {origin}") from error

            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or origin.endswith("/")
            ):
                raise ValueError(f"ALLOWED_ORIGINS must contain exact origins only: {origin}")

            if self.deployment_environment in {"staging", "production"}:
                if parsed.scheme != "https":
                    raise ValueError(
                        f"{self.deployment_environment} origins must use HTTPS: {origin}"
                    )
            elif parsed.scheme == "http" and parsed.hostname not in {
                "localhost",
                "127.0.0.1",
                "::1",
            }:
                raise ValueError(f"development HTTP origins must use a loopback host: {origin}")

        if len(set(origins)) != len(origins):
            raise ValueError("ALLOWED_ORIGINS cannot contain duplicate origins")
        return self

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
