from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ForecastProviderName = Literal["mock", "fourcastnet"]
FourCastNetEndpointMode = Literal["self_hosted", "hosted"]


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

    forecast_provider: ForecastProviderName = "mock"
    fourcastnet_endpoint_mode: FourCastNetEndpointMode = "self_hosted"
    nim_base_url: str = "http://localhost:8000"
    fourcastnet_hosted_url: str = "https://climate.api.nvidia.com/v1/nvidia/fourcastnet"
    nvcf_status_url: str = "https://api.nvcf.nvidia.com/v2/nvcf/pexec/status"
    nvidia_api_key: SecretStr | None = Field(default=None)
    enable_mock_forecast: bool = True
    request_timeout_seconds: int = 300
    nvcf_max_poll_attempts: int = 20
    nvcf_poll_interval_seconds: float = 1
    fourcastnet_cache_enabled: bool = True
    fourcastnet_cache_dir: str = "./data/cache/fourcastnet"


@lru_cache
def get_settings() -> Settings:
    return Settings()

