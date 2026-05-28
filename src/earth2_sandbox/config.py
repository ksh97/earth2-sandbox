from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EARTH2_",
        extra="ignore",
    )

    app_name: str = "earth2-sandbox"
    environment: str = "local"
    log_level: str = "INFO"

    data_dir: str = "./data"
    output_dir: str = "./outputs"
    checkpoint_dir: str = "./checkpoints"

    nim_base_url: str = "http://localhost:8000"
    nvidia_api_key: SecretStr | None = Field(default=None)
    enable_mock_forecast: bool = True
    request_timeout_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()

