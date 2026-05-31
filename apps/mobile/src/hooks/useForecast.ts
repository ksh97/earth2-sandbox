import { useEffect, useMemo, useState } from "react";

import {
  fetchForecastProviderStatus,
  fetchPointForecast,
  ForecastProviderStatus,
  ForecastSummary,
} from "../api/forecast";
import { formatDateTime } from "../utils/forecastFormat";
import { LocationPreset, locationPresets } from "../locations";

const initialLatitude = "37.5665";
const initialLongitude = "126.9780";
const initialPreset = locationPresets[0] ?? null;

export type ScreenMode = "overview" | "details";
export const screenModes: ScreenMode[] = ["overview", "details"];

export function useForecast() {
  const [latitude, setLatitude] = useState(initialLatitude);
  const [longitude, setLongitude] = useState(initialLongitude);
  const [selectedPreset, setSelectedPreset] = useState<LocationPreset | null>(initialPreset);
  const [forecast, setForecast] = useState<ForecastSummary | null>(null);
  const [providerStatus, setProviderStatus] = useState<ForecastProviderStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [providerErrorMessage, setProviderErrorMessage] = useState<string | null>(null);
  const [screenMode, setScreenMode] = useState<ScreenMode>("overview");
  const [selectedLeadHour, setSelectedLeadHour] = useState<number | null>(null);

  const generatedAt = useMemo(() => {
    if (!forecast) {
      return "";
    }

    return formatDateTime(forecast.generated_at);
  }, [forecast]);

  const forecastWindowEnd = useMemo(() => {
    if (!forecast) {
      return "";
    }

    return formatDateTime(forecast.forecast_window.end_at);
  }, [forecast]);

  const timeline = forecast?.timeline ?? [];
  const selectedTimelineStep = useMemo(() => {
    if (timeline.length === 0) {
      return null;
    }

    return (
      timeline.find((step) => step.lead_time_hours === selectedLeadHour) ??
      timeline[0] ??
      null
    );
  }, [selectedLeadHour, timeline]);

  const syncState =
    errorMessage || providerErrorMessage ? "Offline" : isLoading ? "Syncing" : "Ready";

  async function refreshProviderStatus() {
    try {
      const nextStatus = await fetchForecastProviderStatus();
      setProviderStatus(nextStatus);
      setProviderErrorMessage(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Provider status request failed.";
      setProviderStatus(null);
      setProviderErrorMessage(message);
    }
  }

  async function refreshForecast(nextCoordinates?: { latitude: string; longitude: string }) {
    const requestLatitude = nextCoordinates?.latitude ?? latitude;
    const requestLongitude = nextCoordinates?.longitude ?? longitude;
    const parsedLatitude = Number(requestLatitude);
    const parsedLongitude = Number(requestLongitude);

    if (!Number.isFinite(parsedLatitude) || !Number.isFinite(parsedLongitude)) {
      setErrorMessage("Enter numeric coordinates.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextForecast = await fetchPointForecast({
        latitude: parsedLatitude,
        longitude: parsedLongitude,
      });
      setForecast(nextForecast);
      setSelectedLeadHour(nextForecast.timeline[0]?.lead_time_hours ?? null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Forecast request failed.";
      setForecast(null);
      setErrorMessage(message);
      setSelectedLeadHour(null);
    } finally {
      setIsLoading(false);
    }
  }

  function choosePreset(preset: LocationPreset) {
    setSelectedPreset(preset);
    setLatitude(preset.latitude);
    setLongitude(preset.longitude);
    void refreshForecast({
      latitude: preset.latitude,
      longitude: preset.longitude,
    });
  }

  function updateLatitude(value: string) {
    setSelectedPreset(null);
    setLatitude(value);
  }

  function updateLongitude(value: string) {
    setSelectedPreset(null);
    setLongitude(value);
  }

  useEffect(() => {
    void refreshProviderStatus();
    void refreshForecast();
  }, []);

  return {
    choosePreset,
    errorMessage,
    forecast,
    forecastWindowEnd,
    generatedAt,
    isLoading,
    latitude,
    longitude,
    providerErrorMessage,
    providerStatus,
    refreshForecast,
    refreshProviderStatus,
    screenMode,
    selectedPreset,
    selectedTimelineStep,
    setScreenMode,
    setSelectedLeadHour,
    syncState,
    timeline,
    updateLatitude,
    updateLongitude,
  };
}
