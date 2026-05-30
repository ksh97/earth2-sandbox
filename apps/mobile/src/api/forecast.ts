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
    throw new Error(`Forecast API returned ${response.status}.`);
  }

  return (await response.json()) as ForecastSummary;
}
