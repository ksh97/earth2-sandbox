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
    fourcastnet_input_array_path: str | None = None
    fourcastnet_input_time: str = "2023-01-01T00:00:00Z"
    fourcastnet_simulation_length: int = Field(default=1, ge=1, le=40)
    fourcastnet_summary_lead_hours: int = Field(default=6, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
