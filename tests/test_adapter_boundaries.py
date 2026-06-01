from earth2_sandbox.clients.nim import FourCastNetNimClient as LegacyFourCastNetNimClient
from earth2_sandbox.infrastructure.nvidia import (
    FourCastNetForecastProvider,
    FourCastNetNimClient,
    FourCastNetPostProcessor,
)
from earth2_sandbox.infrastructure.nvidia.fourcastnet_decoder import (
    FourCastNetPostProcessor as InfrastructureFourCastNetPostProcessor,
)
from earth2_sandbox.infrastructure.nvidia.fourcastnet_provider import (
    FourCastNetForecastProvider as InfrastructureFourCastNetForecastProvider,
)
from earth2_sandbox.infrastructure.providers import MockForecastProvider
from earth2_sandbox.postprocessing import FourCastNetPostProcessor as LegacyFourCastNetPostProcessor
from earth2_sandbox.providers import (
    FourCastNetForecastProvider as PublicFourCastNetForecastProvider,
)
from earth2_sandbox.providers import MockForecastProvider as PublicMockForecastProvider
from earth2_sandbox.providers.fourcastnet import (
    FourCastNetForecastProvider as LegacyFourCastNetForecastProvider,
)
from earth2_sandbox.providers.mock import MockForecastProvider as LegacyMockForecastProvider


def test_new_adapter_paths_are_primary_exports() -> None:
    assert FourCastNetForecastProvider is InfrastructureFourCastNetForecastProvider
    assert FourCastNetPostProcessor is InfrastructureFourCastNetPostProcessor
    assert FourCastNetNimClient is LegacyFourCastNetNimClient
    assert MockForecastProvider is PublicMockForecastProvider


def test_legacy_adapter_paths_remain_compatibility_exports() -> None:
    assert LegacyFourCastNetForecastProvider is FourCastNetForecastProvider
    assert PublicFourCastNetForecastProvider is FourCastNetForecastProvider
    assert LegacyMockForecastProvider is MockForecastProvider
    assert LegacyFourCastNetPostProcessor is FourCastNetPostProcessor

