import { Platform } from "react-native";

export type ForecastMetric = {
  name: "temperature" | "wind_speed" | "humidity" | string;
  value: number;
  unit: "celsius" | "m/s" | "percent" | string;
};

export type ForecastModelInfo = {
  name: string;
  version: string;
  resolution: string;
  run_mode: "mock" | "nim";
};

export type ForecastWindow = {
  start_at: string;
  end_at: string;
  step_hours: number;
  lead_hours: number[];
};

export type ForecastCondition = "clear" | "breezy" | "humid" | "rain_watch";

export type ForecastTimelineStep = {
  lead_time_hours: number;
  valid_at: string;
  temperature_c: number;
  wind_speed_ms: number;
  humidity_percent: number;
  precipitation_probability_percent: number;
  pressure_hpa: number;
  confidence: number;
  condition: ForecastCondition;
  summary: string;
};

export type ForecastSignal = {
  name: string;
  level: "low" | "moderate" | "elevated";
  message: string;
};

export type ForecastSummary = {
  provider: "mock" | "fourcastnet";
  generated_at: string;
  latitude: number;
  longitude: number;
  headline: string;
  metrics: ForecastMetric[];
  model: ForecastModelInfo;
  forecast_window: ForecastWindow;
  timeline: ForecastTimelineStep[];
  signals: ForecastSignal[];
};

export type ForecastProviderStatus = {
  provider: "mock" | "fourcastnet";
  mode: string;
  configured: boolean;
  ready: boolean;
  supports_point_forecast: boolean;
  endpoint: string | null;
  detail: string;
};

type ForecastRequest = {
  latitude: number;
  longitude: number;
};

const fallbackBaseUrl = Platform.select({
  android: "http://10.0.2.2:8000",
  default: "http://127.0.0.1:8000",
});

const apiBaseUrl =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? fallbackBaseUrl ?? "http://127.0.0.1:8000";

export async function fetchSampleForecast({
  latitude,
  longitude,
}: ForecastRequest): Promise<ForecastSummary> {
  const query = `latitude=${encodeURIComponent(String(latitude))}&longitude=${encodeURIComponent(
    String(longitude),
  )}`;
  const response = await fetch(`${apiBaseUrl}/api/v1/forecast/sample?${query}`);

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Forecast API"));
  }

  return parseForecastSummary(await readJson(response, "Forecast API"));
}

export async function fetchForecastProviderStatus(): Promise<ForecastProviderStatus> {
  const response = await fetch(`${apiBaseUrl}/api/v1/forecast/provider/status`);

  if (!response.ok) {
    throw new Error(await formatApiError(response, "Provider status API"));
  }

  return parseForecastProviderStatus(await readJson(response, "Provider status API"));
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
    return detail ? `${label} returned ${response.status}: ${detail}` : `${label} returned ${response.status}.`;
  } catch {
    return `${label} returned ${response.status}.`;
  }
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
