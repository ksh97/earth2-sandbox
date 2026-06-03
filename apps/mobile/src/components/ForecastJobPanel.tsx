import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { ForecastJob, ForecastJobPollResponse, ForecastJobStatus } from "../api/forecast";
import { colors, spacing } from "../theme";
import { formatDateTime } from "../utils/forecastFormat";
import { ForecastDiagnosticsSummary } from "./ForecastDiagnosticsSummary";

type ForecastJobPanelProps = {
  job: ForecastJob | null;
  poll: ForecastJobPollResponse | null;
  isPolling: boolean;
  onCancelJob: (job: ForecastJob) => void;
  onRetryJob: (job: ForecastJob) => void;
};

export function ForecastJobPanel({
  job,
  poll,
  isPolling,
  onCancelJob,
  onRetryJob,
}: ForecastJobPanelProps) {
  const status = poll?.status ?? job?.status ?? null;
  const canCancel = job ? status === "queued" || status === "running" : false;
  const canRetry = job ? isTerminalStatus(status) : false;
  const latestMessage =
    poll?.latest_event?.message ??
    job?.events[job.events.length - 1]?.message ??
    "Forecast jobs will appear here after the first request.";
  const updatedAt = poll?.updated_at ?? job?.updated_at ?? null;

  return (
    <View style={styles.panel}>
      <View style={styles.header}>
        <View style={styles.titleGroup}>
          <Text style={styles.label}>Forecast job</Text>
          <Text style={styles.title}>{job ? shortJobId(job.id) : "Waiting"}</Text>
        </View>
        <View style={styles.statusGroup}>
          {isPolling && !poll?.terminal ? <ActivityIndicator color={colors.accent} /> : null}
          <Text style={[styles.badge, status ? badgeStyle(status) : styles.badgeIdle]}>
            {status ? formatJobStatus(status) : "Idle"}
          </Text>
        </View>
      </View>

      <Text style={styles.message}>{latestMessage}</Text>

      <View style={styles.metaGrid}>
        <JobMeta label="Attempt" value={job ? String(job.attempt) : "-"} />
        <JobMeta label="Events" value={String(poll?.event_count ?? job?.events.length ?? 0)} />
        <JobMeta
          label="Forecast"
          value={job ? (poll?.forecast_ready ? "Ready" : "Pending") : "-"}
        />
        <JobMeta label="Updated" value={updatedAt ? formatDateTime(updatedAt) : "-"} />
      </View>

      {job ? (
        <ForecastDiagnosticsSummary
          diagnostics={job.diagnostics}
          error={job.error}
          isFailed={status === "failed"}
        />
      ) : null}

      {job && (canCancel || canRetry) ? (
        <View style={styles.actionRow}>
          {canCancel ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => onCancelJob(job)}
              style={({ pressed }) => [styles.secondaryButton, pressed && styles.buttonPressed]}
            >
              <Text style={styles.secondaryButtonText}>Cancel</Text>
            </Pressable>
          ) : null}
          {canRetry ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => onRetryJob(job)}
              style={({ pressed }) => [styles.primaryButton, pressed && styles.buttonPressed]}
            >
              <Text style={styles.primaryButtonText}>Retry</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

function JobMeta({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metaItem}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text numberOfLines={2} style={styles.metaValue}>
        {value}
      </Text>
    </View>
  );
}

function shortJobId(jobId: string) {
  return `Job ${jobId.slice(0, 8)}`;
}

function formatJobStatus(status: ForecastJobStatus) {
  const statusMap: Record<ForecastJobStatus, string> = {
    cancelled: "Cancelled",
    failed: "Failed",
    queued: "Queued",
    running: "Running",
    succeeded: "Succeeded",
  };

  return statusMap[status];
}

function badgeStyle(status: ForecastJobStatus) {
  if (status === "succeeded") {
    return styles.badgeReady;
  }

  if (status === "failed" || status === "cancelled") {
    return styles.badgeStopped;
  }

  return styles.badgeActive;
}

function isTerminalStatus(status: ForecastJobStatus | null) {
  return status === "succeeded" || status === "failed" || status === "cancelled";
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
  statusGroup: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.sm,
    minHeight: 30,
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
  badgeActive: {
    backgroundColor: colors.badge,
  },
  badgeIdle: {
    backgroundColor: colors.input,
  },
  badgeReady: {
    backgroundColor: colors.accentSoft,
  },
  badgeStopped: {
    backgroundColor: colors.errorSurface,
    color: colors.error,
  },
  message: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
  },
  metaGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metaItem: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexGrow: 1,
    minWidth: 120,
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
  actionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: colors.accent,
    borderRadius: 8,
    minHeight: 38,
    justifyContent: "center",
    minWidth: 96,
    paddingHorizontal: spacing.md,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  secondaryButton: {
    alignItems: "center",
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 38,
    justifyContent: "center",
    minWidth: 96,
    paddingHorizontal: spacing.md,
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  buttonPressed: {
    opacity: 0.82,
  },
});
