from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

Labels = tuple[tuple[str, str], ...]

HTTP_REQUESTS_TOTAL = "earth2_http_requests_total"
HTTP_REQUEST_DURATION_SECONDS = "earth2_http_request_duration_seconds"
FORECAST_JOBS_TOTAL = "earth2_forecast_jobs_total"


@dataclass
class MetricsRegistry:
    _lock: Lock = field(default_factory=Lock)
    _http_request_counts: dict[Labels, int] = field(default_factory=dict)
    _http_request_duration_sums: dict[Labels, float] = field(default_factory=dict)
    _forecast_job_counts: dict[Labels, int] = field(default_factory=dict)

    def record_http_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        labels = _labels(
            method=method.upper(),
            path=path,
            status_code=str(status_code),
        )
        with self._lock:
            self._http_request_counts[labels] = self._http_request_counts.get(labels, 0) + 1
            self._http_request_duration_sums[labels] = (
                self._http_request_duration_sums.get(labels, 0.0) + duration_seconds
            )

    def increment_forecast_job_event(self, event: str) -> None:
        labels = _labels(event=event)
        with self._lock:
            self._forecast_job_counts[labels] = self._forecast_job_counts.get(labels, 0) + 1

    def render_prometheus(self) -> str:
        with self._lock:
            http_counts = sorted(self._http_request_counts.items())
            duration_sums = sorted(self._http_request_duration_sums.items())
            job_counts = sorted(self._forecast_job_counts.items())

        lines = [
            "# HELP earth2_http_requests_total Total HTTP requests observed by the backend.",
            "# TYPE earth2_http_requests_total counter",
        ]
        lines.extend(_sample(HTTP_REQUESTS_TOTAL, labels, count) for labels, count in http_counts)

        lines.extend(
            [
                "# HELP earth2_http_request_duration_seconds HTTP request duration in seconds.",
                "# TYPE earth2_http_request_duration_seconds summary",
            ]
        )
        lines.extend(
            _sample(f"{HTTP_REQUEST_DURATION_SECONDS}_count", labels, count)
            for labels, count in http_counts
        )
        lines.extend(
            _sample(f"{HTTP_REQUEST_DURATION_SECONDS}_sum", labels, duration_sum)
            for labels, duration_sum in duration_sums
        )

        lines.extend(
            [
                "# HELP earth2_forecast_jobs_total Total forecast job lifecycle events.",
                "# TYPE earth2_forecast_jobs_total counter",
            ]
        )
        lines.extend(_sample(FORECAST_JOBS_TOTAL, labels, count) for labels, count in job_counts)
        return "\n".join(lines) + "\n"


default_registry = MetricsRegistry()


def record_http_request(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    default_registry.record_http_request(
        method=method,
        path=path,
        status_code=status_code,
        duration_seconds=duration_seconds,
    )


def increment_forecast_job_event(event: str) -> None:
    default_registry.increment_forecast_job_event(event)


def render_prometheus() -> str:
    return default_registry.render_prometheus()


def _labels(**labels: str) -> Labels:
    return tuple(sorted((key, str(value)) for key, value in labels.items()))


def _sample(name: str, labels: Labels, value: float | int) -> str:
    label_text = ",".join(
        f'{key}="{_escape_label_value(value)}"' for key, value in labels
    )
    label_suffix = f"{{{label_text}}}" if label_text else ""
    return f"{name}{label_suffix} {value}"


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

