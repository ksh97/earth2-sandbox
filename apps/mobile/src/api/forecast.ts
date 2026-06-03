import { Platform } from "react-native";

import type { components, paths } from "../generated/earth2-api/schema";

export type ForecastMetric = components["schemas"]["ForecastMetric"];
export type ForecastModelInfo = components["schemas"]["ForecastModelInfo"];
export type ForecastWindow = components["schemas"]["ForecastWindow"];
export type ForecastCondition = components["schemas"]["ForecastTimelineStep"]["condition"];
export type ForecastTimelineStep = components["schemas"]["ForecastTimelineStep"];
export type ForecastSignal = components["schemas"]["ForecastSignal"];
export type ForecastSummary = components["schemas"]["ForecastSummary"];
export type ForecastProviderStatus = components["schemas"]["ForecastProviderStatus"] & {
  endpoint: string | null;
};
export type ForecastJobStatus = components["schemas"]["ForecastJob"]["status"];
export type ForecastJobEvent = components["schemas"]["ForecastJobEvent"];
export type ForecastJobDiagnostics = components["schemas"]["ForecastJobDiagnostics"] & {
  provider: string | null;
  response_source: string | null;
  cache_status: string | null;
  cached_artifact_id: string | null;
  nvcf_request_id: string | null;
  nvcf_status: string | null;
  poll_attempts: number;
  response_reference_present: boolean;
  byte_length: number | null;
  sha256: string | null;
  message: string | null;
};
export type ForecastJob = components["schemas"]["ForecastJob"] & {
  parent_job_id: string | null;
  attempt: number;
  started_at: string | null;
  completed_at: string | null;
  forecast: ForecastSummary | null;
  diagnostics: ForecastJobDiagnostics | null;
  events: ForecastJobEvent[];
  error: string | null;
  links: Record<string, string>;
};
export type ForecastJobPollResponse = components["schemas"]["ForecastJobPollResponse"] & {
  retry_after_seconds: number | null;
  latest_event: ForecastJobEvent | null;
  links: Record<string, string>;
};
export type ForecastJobSummary = components["schemas"]["ForecastJobSummary"] & {
  parent_job_id: string | null;
  attempt: number;
  completed_at: string | null;
  diagnostics: ForecastJobDiagnostics | null;
  error: string | null;
  links: Record<string, string>;
};
export type ForecastJobListResponse = components["schemas"]["ForecastJobListResponse"] & {
  jobs: ForecastJobSummary[];
};

type ForecastPointQuery =
  paths["/api/v1/forecast/point"]["get"]["parameters"]["query"];
type ForecastRequest =
  paths["/api/v1/forecast/jobs"]["post"]["requestBody"]["content"]["application/json"];
type ForecastJobListQuery =
  paths["/api/v1/forecast/jobs"]["get"]["parameters"]["query"];

const fallbackBaseUrl = Platform.select({
  android: "http://10.0.2.2:8000",
  default: "http://127.0.0.1:8000",
});

export const forecastApiBaseUrl =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? fallbackBaseUrl ?? "http://127.0.0.1:8000";

export async function fetchPointForecast({
  latitude,
  longitude,
}: ForecastPointQuery): Promise<ForecastSummary> {
  const query = `latitude=${encodeURIComponent(String(latitude))}&longitude=${encodeURIComponent(
    String(longitude),
  )}`;
  const response = await fetch(`${forecastApiBaseUrl}/api/v1/forecast/point?${query}`);

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Forecast API"));
  }

  return parseForecastSummary(await readJson(response, "Forecast API"));
}

export async function fetchForecastProviderStatus(): Promise<ForecastProviderStatus> {
  const response = await fetch(`${forecastApiBaseUrl}/api/v1/forecast/provider/status`);

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Provider status API"));
  }

  return parseForecastProviderStatus(await readJson(response, "Provider status API"));
}

export async function createForecastJob(request: ForecastRequest): Promise<ForecastJob> {
  const response = await fetch(`${forecastApiBaseUrl}/api/v1/forecast/jobs`, {
    body: JSON.stringify(request),
    headers: {
      "content-type": "application/json",
    },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Forecast job API"));
  }

  return parseForecastJob(await readJson(response, "Forecast job API"));
}

export async function listForecastJobs({
  limit = 20,
  status = null,
}: ForecastJobListQuery = {}): Promise<ForecastJobListResponse> {
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (status) {
    searchParams.set("status", status);
  }
  const response = await fetch(`${forecastApiBaseUrl}/api/v1/forecast/jobs?${searchParams}`);

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Forecast job history API"));
  }

  return parseForecastJobListResponse(await readJson(response, "Forecast job history API"));
}

export async function fetchForecastJob(pathOrUrl: string): Promise<ForecastJob> {
  const response = await fetch(buildApiUrl(pathOrUrl));

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Forecast job API"));
  }

  return parseForecastJob(await readJson(response, "Forecast job API"));
}

export async function cancelForecastJob(pathOrUrl: string): Promise<ForecastJob> {
  const response = await fetch(buildApiUrl(pathOrUrl), {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Forecast job cancel API"));
  }

  return parseForecastJob(await readJson(response, "Forecast job cancel API"));
}

export async function retryForecastJob(pathOrUrl: string): Promise<ForecastJob> {
  const response = await fetch(buildApiUrl(pathOrUrl), {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Forecast job retry API"));
  }

  return parseForecastJob(await readJson(response, "Forecast job retry API"));
}

export async function pollForecastJob(pathOrUrl: string): Promise<ForecastJobPollResponse> {
  const response = await fetch(buildApiUrl(pathOrUrl));

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Forecast job poll API"));
  }

  return parseForecastJobPollResponse(await readJson(response, "Forecast job poll API"));
}

function buildApiUrl(pathOrUrl: string) {
  if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) {
    return pathOrUrl;
  }

  return `${forecastApiBaseUrl}${pathOrUrl}`;
}

async function readJson(response: Response, label: string): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new Error(`${label} returned invalid JSON.`);
  }
}

async function formatApiError(response: Response, label: string) {
  try {
    const payload = await response.json();
    const detail = isRecord(payload) && typeof payload.detail === "string" ? payload.detail : "";
    const message = detail
      ? `${label} returned ${response.status}: ${detail}`
      : `${label} returned ${response.status}.`;
    return formatActionableApiError(message);
  } catch {
    return formatActionableApiError(`${label} returned ${response.status}.`);
  }
}

function formatActionableApiError(message: string) {
  if (message.includes("Hosted FourCastNet returned 504")) {
    return (
      "Hosted FourCastNet did not return a forecast body yet. " +
      "The local backend is reachable, but the hosted provider needs retry or asset-download handling."
    );
  }

  if (message.includes("large asset marker")) {
    return (
      "Hosted FourCastNet returned a large-result marker instead of forecast bytes. " +
      "The backend needs output asset download handling before this can be sampled on the map."
    );
  }

  return message;
}

function parseForecastSummary(payload: unknown): ForecastSummary {
  if (!isForecastSummary(payload)) {
    throw new Error("Forecast API returned an unexpected forecast payload.");
  }

  return payload;
}

function parseForecastProviderStatus(payload: unknown): ForecastProviderStatus {
  if (!isForecastProviderStatus(payload)) {
    throw new Error("Provider status API returned an unexpected payload.");
  }

  return payload;
}

function parseForecastJob(payload: unknown): ForecastJob {
  if (!isForecastJob(payload)) {
    throw new Error("Forecast job API returned an unexpected payload.");
  }

  return payload;
}

function parseForecastJobListResponse(payload: unknown): ForecastJobListResponse {
  if (!isForecastJobListResponse(payload)) {
    throw new Error("Forecast job history API returned an unexpected payload.");
  }

  return payload;
}

function parseForecastJobPollResponse(payload: unknown): ForecastJobPollResponse {
  if (!isForecastJobPollResponse(payload)) {
    throw new Error("Forecast job poll API returned an unexpected payload.");
  }

  return payload;
}

function isForecastJobListResponse(value: unknown): value is ForecastJobListResponse {
  return (
    isRecord(value) &&
    typeof value.count === "number" &&
    Array.isArray(value.jobs) &&
    value.jobs.every(isForecastJobSummary)
  );
}

function isForecastSummary(value: unknown): value is ForecastSummary {
  return (
    isRecord(value) &&
    isForecastProvider(value.provider) &&
    typeof value.generated_at === "string" &&
    typeof value.latitude === "number" &&
    typeof value.longitude === "number" &&
    typeof value.headline === "string" &&
    Array.isArray(value.metrics) &&
    value.metrics.every(isForecastMetric) &&
    isForecastModelInfo(value.model) &&
    isForecastWindow(value.forecast_window) &&
    Array.isArray(value.timeline) &&
    value.timeline.every(isForecastTimelineStep) &&
    Array.isArray(value.signals) &&
    value.signals.every(isForecastSignal)
  );
}

function isForecastJobSummary(value: unknown): value is ForecastJobSummary {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    isForecastJobStatus(value.status) &&
    typeof value.latitude === "number" &&
    typeof value.longitude === "number" &&
    (typeof value.parent_job_id === "string" || value.parent_job_id === null) &&
    typeof value.attempt === "number" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string" &&
    (typeof value.completed_at === "string" || value.completed_at === null) &&
    (isForecastJobDiagnostics(value.diagnostics) || value.diagnostics === null) &&
    (typeof value.error === "string" || value.error === null) &&
    isStringRecord(value.links)
  );
}

function isForecastJob(value: unknown): value is ForecastJob {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    isForecastJobStatus(value.status) &&
    typeof value.latitude === "number" &&
    typeof value.longitude === "number" &&
    (typeof value.parent_job_id === "string" || value.parent_job_id === null) &&
    typeof value.attempt === "number" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string" &&
    (typeof value.started_at === "string" || value.started_at === null) &&
    (typeof value.completed_at === "string" || value.completed_at === null) &&
    (isForecastSummary(value.forecast) || value.forecast === null) &&
    (isForecastJobDiagnostics(value.diagnostics) || value.diagnostics === null) &&
    Array.isArray(value.events) &&
    value.events.every(isForecastJobEvent) &&
    (typeof value.error === "string" || value.error === null) &&
    isStringRecord(value.links)
  );
}

function isForecastJobPollResponse(value: unknown): value is ForecastJobPollResponse {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    isForecastJobStatus(value.status) &&
    typeof value.terminal === "boolean" &&
    typeof value.forecast_ready === "boolean" &&
    typeof value.updated_at === "string" &&
    (typeof value.retry_after_seconds === "number" || value.retry_after_seconds === null) &&
    typeof value.event_count === "number" &&
    (isForecastJobEvent(value.latest_event) || value.latest_event === null) &&
    isStringRecord(value.links)
  );
}

function isForecastJobDiagnostics(value: unknown): value is ForecastJobDiagnostics {
  return (
    isRecord(value) &&
    (typeof value.provider === "string" || value.provider === null) &&
    (typeof value.response_source === "string" || value.response_source === null) &&
    (typeof value.cache_status === "string" || value.cache_status === null) &&
    (typeof value.cached_artifact_id === "string" || value.cached_artifact_id === null) &&
    (typeof value.nvcf_request_id === "string" || value.nvcf_request_id === null) &&
    (typeof value.nvcf_status === "string" || value.nvcf_status === null) &&
    typeof value.poll_attempts === "number" &&
    typeof value.response_reference_present === "boolean" &&
    (typeof value.byte_length === "number" || value.byte_length === null) &&
    (typeof value.sha256 === "string" || value.sha256 === null) &&
    (typeof value.message === "string" || value.message === null)
  );
}

function isForecastJobEvent(value: unknown): value is ForecastJobEvent {
  return (
    isRecord(value) &&
    typeof value.occurred_at === "string" &&
    isForecastJobStatus(value.status) &&
    typeof value.message === "string"
  );
}

function isForecastJobStatus(value: unknown): value is ForecastJobStatus {
  return (
    value === "queued" ||
    value === "running" ||
    value === "succeeded" ||
    value === "failed" ||
    value === "cancelled"
  );
}

function isForecastProviderStatus(value: unknown): value is ForecastProviderStatus {
  return (
    isRecord(value) &&
    isForecastProvider(value.provider) &&
    typeof value.mode === "string" &&
    typeof value.configured === "boolean" &&
    typeof value.ready === "boolean" &&
    typeof value.supports_point_forecast === "boolean" &&
    (typeof value.endpoint === "string" || value.endpoint === null) &&
    typeof value.detail === "string"
  );
}

function isForecastMetric(value: unknown): value is ForecastMetric {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.value === "number" &&
    typeof value.unit === "string"
  );
}

function isForecastModelInfo(value: unknown): value is ForecastModelInfo {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.version === "string" &&
    typeof value.resolution === "string" &&
    (value.run_mode === "mock" || value.run_mode === "nim")
  );
}

function isForecastWindow(value: unknown): value is ForecastWindow {
  return (
    isRecord(value) &&
    typeof value.start_at === "string" &&
    typeof value.end_at === "string" &&
    typeof value.step_hours === "number" &&
    Array.isArray(value.lead_hours) &&
    value.lead_hours.every((leadHour) => typeof leadHour === "number")
  );
}

function isForecastTimelineStep(value: unknown): value is ForecastTimelineStep {
  return (
    isRecord(value) &&
    typeof value.lead_time_hours === "number" &&
    typeof value.valid_at === "string" &&
    typeof value.temperature_c === "number" &&
    typeof value.wind_speed_ms === "number" &&
    typeof value.humidity_percent === "number" &&
    typeof value.precipitation_probability_percent === "number" &&
    typeof value.pressure_hpa === "number" &&
    typeof value.confidence === "number" &&
    isForecastCondition(value.condition) &&
    typeof value.summary === "string"
  );
}

function isForecastSignal(value: unknown): value is ForecastSignal {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    isSignalLevel(value.level) &&
    typeof value.message === "string"
  );
}

function isForecastProvider(value: unknown): value is ForecastSummary["provider"] {
  return value === "mock" || value === "fourcastnet";
}

function isForecastCondition(value: unknown): value is ForecastCondition {
  return value === "clear" || value === "breezy" || value === "humid" || value === "rain_watch";
}

function isSignalLevel(value: unknown): value is ForecastSignal["level"] {
  return value === "low" || value === "moderate" || value === "elevated";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return (
    isRecord(value) &&
    Object.values(value).every((entry) => typeof entry === "string")
  );
}
