from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    allowed_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    model_path: str = "models/nail-segmentation.onnx"
    model_version: str = "unavailable"
    max_encoded_bytes: int = 12 * 1024 * 1024
    max_decoded_pixels: int = 25_000_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
