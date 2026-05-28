import { Platform } from "react-native";

export type ForecastMetric = {
  name: "temperature" | "wind_speed" | "humidity" | string;
  value: number;
  unit: "celsius" | "m/s" | "percent" | string;
};

export type ForecastSummary = {
  provider: "mock" | "fourcastnet";
  generated_at: string;
  latitude: number;
  longitude: number;
  headline: string;
  metrics: ForecastMetric[];
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
