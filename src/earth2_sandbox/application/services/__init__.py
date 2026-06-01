"""Application services that coordinate forecast job commands and queries."""

__all__ = [
    "DiagnosticForecastProvider",
    "ForecastJobCommandService",
    "ForecastJobQueryService",
    "ForecastJobRecoveryReport",
    "ForecastJobRecoveryService",
]


def __getattr__(name: str):
    if name in {"DiagnosticForecastProvider", "ForecastJobCommandService"}:
        from earth2_sandbox.application.services.forecast_job_command_service import (
            DiagnosticForecastProvider,
            ForecastJobCommandService,
        )

        exports = {
            "DiagnosticForecastProvider": DiagnosticForecastProvider,
            "ForecastJobCommandService": ForecastJobCommandService,
        }
        return exports[name]

    if name == "ForecastJobQueryService":
        from earth2_sandbox.application.services.forecast_job_query_service import (
            ForecastJobQueryService,
        )

        return ForecastJobQueryService

    if name in {"ForecastJobRecoveryReport", "ForecastJobRecoveryService"}:
        from earth2_sandbox.application.services.forecast_job_recovery_service import (
            ForecastJobRecoveryReport,
            ForecastJobRecoveryService,
        )

        exports = {
            "ForecastJobRecoveryReport": ForecastJobRecoveryReport,
            "ForecastJobRecoveryService": ForecastJobRecoveryService,
        }
        return exports[name]

    raise AttributeError(name)
