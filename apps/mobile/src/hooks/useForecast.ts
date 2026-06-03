import { useEffect, useMemo, useRef, useState } from "react";

import {
  cancelForecastJob,
  createForecastJob,
  fetchForecastProviderStatus,
  fetchForecastJob,
  ForecastJobSummary,
  ForecastJobStatus,
  ForecastProviderStatus,
  ForecastSummary,
  ForecastJob,
  ForecastJobPollResponse,
  listForecastJobs,
  pollForecastJob,
  retryForecastJob,
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
export type JobHistoryFilter = "all" | ForecastJobStatus;
export const jobHistoryFilters: JobHistoryFilter[] = [
  "all",
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancelled",
];

export function useForecast() {
  const [latitude, setLatitude] = useState(initialLatitude);
  const [longitude, setLongitude] = useState(initialLongitude);
  const [selectedPreset, setSelectedPreset] = useState<LocationPreset | null>(initialPreset);
  const [forecast, setForecast] = useState<ForecastSummary | null>(null);
  const [forecastJob, setForecastJob] = useState<ForecastJob | null>(null);
  const [forecastJobPoll, setForecastJobPoll] = useState<ForecastJobPollResponse | null>(null);
  const [jobHistory, setJobHistory] = useState<ForecastJobSummary[]>([]);
  const [jobHistoryFilter, setJobHistoryFilter] = useState<JobHistoryFilter>("all");
  const [providerStatus, setProviderStatus] = useState<ForecastProviderStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isJobPolling, setIsJobPolling] = useState(false);
  const [isJobHistoryLoading, setIsJobHistoryLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [jobHistoryErrorMessage, setJobHistoryErrorMessage] = useState<string | null>(null);
  const [jobActionMessage, setJobActionMessage] = useState<string | null>(null);
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

  async function refreshJobHistory(nextFilter: JobHistoryFilter = jobHistoryFilter) {
    setIsJobHistoryLoading(true);
    setJobHistoryErrorMessage(null);

    try {
      const history = await listForecastJobs({
        limit: 20,
        status: nextFilter === "all" ? null : nextFilter,
      });
      setJobHistory(history.jobs);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Forecast job history failed.";
      setJobHistoryErrorMessage(message);
    } finally {
      setIsJobHistoryLoading(false);
    }
  }

  function updateJobHistoryFilter(nextFilter: JobHistoryFilter) {
    setJobHistoryFilter(nextFilter);
    void refreshJobHistory(nextFilter);
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
    setJobActionMessage(null);

    let startedJobId: string | null = null;

    try {
      const job = await createForecastJob({
        latitude: parsedLatitude,
        longitude: parsedLongitude,
      });
      startedJobId = job.id;
      await trackForecastJob(job);
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

  async function cancelJob(job: ForecastJob | ForecastJobSummary) {
    setJobActionMessage(null);
    setJobHistoryErrorMessage(null);

    try {
      const cancelled = await cancelForecastJob(getJobLink(job, "cancel"));
      if (forecastJob?.id === cancelled.id) {
        activeJobId.current = null;
        setForecastJob(cancelled);
        setForecastJobPoll(jobToPollResponse(cancelled));
        setIsLoading(false);
        setIsJobPolling(false);
      }
      setJobActionMessage(`Cancelled ${shortJobId(cancelled.id)}.`);
      await refreshJobHistory();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Forecast job cancel failed.";
      setJobHistoryErrorMessage(message);
    }
  }

  async function retryJob(job: ForecastJob | ForecastJobSummary) {
    setIsLoading(true);
    setIsJobPolling(true);
    setErrorMessage(null);
    setJobActionMessage(null);
    setJobHistoryErrorMessage(null);

    let retryJobId: string | null = null;

    try {
      const retry = await retryForecastJob(getJobLink(job, "retry"));
      retryJobId = retry.id;
      setJobActionMessage(`Retry accepted for ${shortJobId(job.id)}.`);
      await trackForecastJob(retry);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Forecast job retry failed.";
      setForecast(null);
      setErrorMessage(message);
      setSelectedLeadHour(null);
    } finally {
      const isCurrentRequest = retryJobId === null || activeJobId.current === retryJobId;
      if (isCurrentRequest) {
        activeJobId.current = null;
        setIsLoading(false);
        setIsJobPolling(false);
      }
    }
  }

  async function trackForecastJob(job: ForecastJob) {
    activeJobId.current = job.id;
    setForecastJob(job);
    setForecastJobPoll(jobToPollResponse(job));
    void refreshJobHistory();

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
    void refreshJobHistory();

    if (completedJob.status !== "succeeded" || !completedJob.forecast) {
      throw new Error(completedJob.error ?? `Forecast job ${completedJob.status}.`);
    }

    setForecast(completedJob.forecast);
    setSelectedLeadHour(completedJob.forecast.timeline[0]?.lead_time_hours ?? null);
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
    void refreshJobHistory();
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
    isJobHistoryLoading,
    isJobPolling,
    isLoading,
    jobActionMessage,
    jobHistory,
    jobHistoryErrorMessage,
    jobHistoryFilter,
    latitude,
    longitude,
    providerErrorMessage,
    providerStatus,
    refreshForecast,
    refreshJobHistory,
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
    updateJobHistoryFilter,
    cancelJob,
    retryJob,
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

function getJobLink(
  job: ForecastJob | ForecastJobSummary,
  key: "poll" | "self" | "retry" | "cancel",
) {
  const link = job.links[key];
  if (!link) {
    throw new Error(`Forecast job response is missing the ${key} link.`);
  }

  return link;
}

function shortJobId(jobId: string) {
  return `Job ${jobId.slice(0, 8)}`;
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
