import { StyleSheet, Text, View } from "react-native";

import {
  ForecastJob,
  ForecastJobDiagnostics,
  ForecastJobSummary,
  ForecastProviderStatus,
  forecastApiBaseUrl,
  isForecastApiKeyConfigured,
} from "../api/forecast";
import { colors, spacing } from "../theme";

type SettingsDebugScreenProps = {
  currentJob: ForecastJob | null;
  providerErrorMessage: string | null;
  providerStatus: ForecastProviderStatus | null;
  recentJobs: ForecastJobSummary[];
};

type DebugRow = {
  label: string;
  value: string;
};

export function SettingsDebugScreen({
  currentJob,
  providerErrorMessage,
  providerStatus,
  recentJobs,
}: SettingsDebugScreenProps) {
  const latestJob = currentJob ?? recentJobs[0] ?? null;
  const diagnostics = latestJob?.diagnostics ?? null;
  const isFourCastNet = providerStatus?.provider === "fourcastnet";
  const guidance = buildGuidance({
    isFourCastNet,
    providerStatus,
  });

  return (
    <View style={styles.panel}>
      <View style={styles.header}>
        <View style={styles.titleGroup}>
          <Text style={styles.label}>Settings</Text>
          <Text style={styles.title}>Debug console</Text>
        </View>
        <Text style={[styles.badge, isFourCastNet ? styles.badgeHosted : styles.badgeMock]}>
          {providerStatus?.provider ?? "unknown"}
        </Text>
      </View>

      <View style={styles.grid}>
        {buildRuntimeRows({ providerErrorMessage, providerStatus }).map((row) => (
          <DebugMeta key={row.label} label={row.label} value={row.value} />
        ))}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Latest job diagnostics</Text>
        <View style={styles.grid}>
          {buildJobRows({ diagnostics, latestJob }).map((row) => (
            <DebugMeta key={row.label} label={row.label} value={row.value} />
          ))}
        </View>
      </View>

      <Text style={styles.guidance}>{guidance}</Text>
    </View>
  );
}

function buildRuntimeRows({
  providerErrorMessage,
  providerStatus,
}: {
  providerErrorMessage: string | null;
  providerStatus: ForecastProviderStatus | null;
}): DebugRow[] {
  return [
    { label: "API base", value: forecastApiBaseUrl },
    { label: "API key", value: isForecastApiKeyConfigured ? "Configured" : "Not configured" },
    { label: "Provider", value: providerStatus?.provider ?? "Unknown" },
    { label: "Mode", value: providerStatus?.mode ?? "Unknown" },
    { label: "Configured", value: providerStatus?.configured ? "Yes" : "No" },
    { label: "Readiness", value: formatReadiness(providerStatus, providerErrorMessage) },
    { label: "Output", value: formatOutputState(providerStatus) },
  ];
}

function buildJobRows({
  diagnostics,
  latestJob,
}: {
  diagnostics: ForecastJobDiagnostics | null;
  latestJob: ForecastJob | ForecastJobSummary | null;
}): DebugRow[] {
  return [
    { label: "Job", value: latestJob ? shortId(latestJob.id) : "None" },
    { label: "Status", value: latestJob?.status ?? "None" },
    { label: "Provider", value: diagnostics?.provider ?? "None" },
    { label: "NVCF", value: diagnostics?.nvcf_status ?? "None" },
    { label: "Request", value: shortId(diagnostics?.nvcf_request_id) },
    { label: "Cache artifact", value: shortId(diagnostics?.cached_artifact_id) },
    { label: "Source", value: diagnostics?.response_source ?? "None" },
    { label: "Reference", value: diagnostics?.response_reference_present ? "Present" : "Missing" },
  ];
}

function formatReadiness(
  providerStatus: ForecastProviderStatus | null,
  providerErrorMessage: string | null,
) {
  if (providerErrorMessage) {
    return "Provider check failed";
  }

  if (!providerStatus) {
    return "Checking";
  }

  return providerStatus.ready ? "Ready" : "Blocked";
}

function formatOutputState(providerStatus: ForecastProviderStatus | null) {
  if (!providerStatus?.supports_point_forecast) {
    return "Blocked";
  }

  return providerStatus.provider === "fourcastnet" ? "Verify by job" : "Ready";
}

function buildGuidance({
  isFourCastNet,
  providerStatus,
}: {
  isFourCastNet: boolean;
  providerStatus: ForecastProviderStatus | null;
}) {
  if (isFourCastNet) {
    return (
      "FourCastNet mode checks the hosted output path. Treat ready/configured as an API key and " +
      "endpoint check; verify real output through a queued job and its diagnostics."
    );
  }

  if (providerStatus?.provider === "mock") {
    return "Mock mode is suitable for UI, polling, retry, and risk-card workflow validation.";
  }

  return "Start the backend and refresh provider status to confirm the active forecast mode.";
}

function shortId(value: string | null | undefined) {
  if (!value) {
    return "None";
  }

  return value.slice(0, 8);
}

function DebugMeta({ label, value }: DebugRow) {
  return (
    <View style={styles.metaItem}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text numberOfLines={2} style={styles.metaValue}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  panel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: spacing.md,
    padding: spacing.md,
  },
  header: {
    alignItems: "flex-start",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    justifyContent: "space-between",
  },
  titleGroup: {
    flex: 1,
    gap: spacing.xs,
    minWidth: 180,
  },
  label: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  title: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: 0,
  },
  badge: {
    borderRadius: 8,
    color: colors.text,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0,
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    textTransform: "uppercase",
  },
  badgeHosted: {
    backgroundColor: colors.badge,
  },
  badgeMock: {
    backgroundColor: colors.accentSoft,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  metaItem: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexGrow: 1,
    minWidth: 132,
    padding: spacing.sm,
  },
  metaLabel: {
    color: colors.muted,
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  metaValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0,
    marginTop: 2,
  },
  guidance: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
  },
});
