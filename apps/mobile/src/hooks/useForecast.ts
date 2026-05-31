import { useEffect, useMemo, useRef, useState } from "react";

import {
  createForecastJob,
  fetchForecastProviderStatus,
  fetchForecastJob,
  ForecastProviderStatus,
  ForecastSummary,
  ForecastJob,
  ForecastJobPollResponse,
  pollForecastJob,
} from "../api/forecast";
import { formatDateTime } from "../utils/forecastFormat";
import { LocationPreset, locationPresets } from "../locations";

const initialLatitude = "37.5665";
const initialLongitude = "126.9780";
const initialPreset = locationPresets[0] ?? null;
const maxJobPollAttempts = 60;
const defaultJobPollDelayMs = 2000;

export type ScreenMode = "overview" | "details";
export const screenModes: ScreenMode[] = ["overview", "details"];

export function useForecast() {
  const [latitude, setLatitude] = useState(initialLatitude);
  const [longitude, setLongitude] = useState(initialLongitude);
  const [selectedPreset, setSelectedPreset] = useState<LocationPreset | null>(initialPreset);
  const [forecast, setForecast] = useState<ForecastSummary | null>(null);
  const [forecastJob, setForecastJob] = useState<ForecastJob | null>(null);
  const [forecastJobPoll, setForecastJobPoll] = useState<ForecastJobPollResponse | null>(null);
  const [providerStatus, setProviderStatus] = useState<ForecastProviderStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isJobPolling, setIsJobPolling] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [providerErrorMessage, setProviderErrorMessage] = useState<string | null>(null);
  const [screenMode, setScreenMode] = useState<ScreenMode>("overview");
  const [selectedLeadHour, setSelectedLeadHour] = useState<number | null>(null);
  const activeJobId = useRef<string | null>(null);

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
    setIsJobPolling(true);
    setErrorMessage(null);

    let startedJobId: string | null = null;

    try {
      const job = await createForecastJob({
        latitude: parsedLatitude,
        longitude: parsedLongitude,
      });
      startedJobId = job.id;
      activeJobId.current = job.id;
      setForecastJob(job);
      setForecastJobPoll(jobToPollResponse(job));

      const finalPoll = await waitForForecastJob(job);
      if (activeJobId.current !== job.id) {
        return;
      }
      setForecastJobPoll(finalPoll);

      const completedJob = await fetchForecastJob(getJobLink(job, "self"));
      if (activeJobId.current !== job.id) {
        return;
      }
      setForecastJob(completedJob);

      if (completedJob.status !== "succeeded" || !completedJob.forecast) {
        throw new Error(completedJob.error ?? `Forecast job ${completedJob.status}.`);
      }

      setForecast(completedJob.forecast);
      setSelectedLeadHour(completedJob.forecast.timeline[0]?.lead_time_hours ?? null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Forecast request failed.";
      setForecast(null);
      setErrorMessage(message);
      setSelectedLeadHour(null);
    } finally {
      const isCurrentRequest = startedJobId === null || activeJobId.current === startedJobId;
      if (isCurrentRequest) {
        activeJobId.current = null;
        setIsLoading(false);
        setIsJobPolling(false);
      }
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
    forecastJob,
    forecastJobPoll,
    forecastWindowEnd,
    generatedAt,
    isJobPolling,
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

async function waitForForecastJob(job: ForecastJob): Promise<ForecastJobPollResponse> {
  const pollLink = getJobLink(job, "poll");
  let latestPoll = await pollForecastJob(pollLink);

  for (let attempt = 0; attempt < maxJobPollAttempts && !latestPoll.terminal; attempt += 1) {
    const retryAfterSeconds = latestPoll.retry_after_seconds ?? defaultJobPollDelayMs / 1000;
    await delay(Math.max(250, retryAfterSeconds * 1000));
    latestPoll = await pollForecastJob(pollLink);
  }

  if (!latestPoll.terminal) {
    throw new Error("Forecast job did not finish before the polling timeout.");
  }

  return latestPoll;
}

function getJobLink(job: ForecastJob, key: "poll" | "self") {
  const link = job.links[key];
  if (!link) {
    throw new Error(`Forecast job response is missing the ${key} link.`);
  }

  return link;
}

function jobToPollResponse(job: ForecastJob): ForecastJobPollResponse {
  const latestEvent = job.events[job.events.length - 1] ?? null;

  return {
    id: job.id,
    status: job.status,
    terminal: ["succeeded", "failed", "cancelled"].includes(job.status),
    forecast_ready: job.forecast !== null,
    updated_at: job.updated_at,
    retry_after_seconds: job.status === "queued" || job.status === "running" ? 2 : null,
    event_count: job.events.length,
    latest_event: latestEvent,
    links: job.links,
  };
}

function delay(milliseconds: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}
