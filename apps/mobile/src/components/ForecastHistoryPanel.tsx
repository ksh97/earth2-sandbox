import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { ForecastJobStatus, ForecastJobSummary } from "../api/forecast";
import type { JobHistoryFilter } from "../hooks/useForecast";
import { colors, spacing } from "../theme";
import { formatDateTime } from "../utils/forecastFormat";
import { ForecastDiagnosticsSummary } from "./ForecastDiagnosticsSummary";

type ForecastHistoryPanelProps = {
  actionMessage: string | null;
  errorMessage: string | null;
  filter: JobHistoryFilter;
  isLoading: boolean;
  jobs: ForecastJobSummary[];
  onCancelJob: (job: ForecastJobSummary) => void;
  onChangeFilter: (filter: JobHistoryFilter) => void;
  onRefresh: () => void;
  onRetryJob: (job: ForecastJobSummary) => void;
};

const filters: JobHistoryFilter[] = [
  "all",
  "queued",
  "running",
  "succeeded",
  "failed",
  "cancelled",
];

export function ForecastHistoryPanel({
  actionMessage,
  errorMessage,
  filter,
  isLoading,
  jobs,
  onCancelJob,
  onChangeFilter,
  onRefresh,
  onRetryJob,
}: ForecastHistoryPanelProps) {
  return (
    <View style={styles.panel}>
      <View style={styles.header}>
        <View style={styles.titleGroup}>
          <Text style={styles.label}>Recent jobs</Text>
          <Text style={styles.title}>Forecast history</Text>
        </View>
        <View style={styles.headerActions}>
          {isLoading ? <ActivityIndicator color={colors.accent} /> : null}
          <Pressable
            accessibilityRole="button"
            onPress={onRefresh}
            style={({ pressed }) => [styles.refreshButton, pressed && styles.buttonPressed]}
          >
            <Text style={styles.refreshText}>Refresh</Text>
          </Pressable>
        </View>
      </View>

      <View style={styles.filterRow}>
        {filters.map((nextFilter) => {
          const selected = filter === nextFilter;
          return (
            <Pressable
              accessibilityRole="button"
              key={nextFilter}
              onPress={() => onChangeFilter(nextFilter)}
              style={({ pressed }) => [
                styles.filterButton,
                selected && styles.filterButtonSelected,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={[styles.filterText, selected && styles.filterTextSelected]}>
                {formatFilter(nextFilter)}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {actionMessage ? <Text style={styles.actionMessage}>{actionMessage}</Text> : null}
      {errorMessage ? <Text style={styles.errorMessage}>{errorMessage}</Text> : null}

      <View style={styles.jobList}>
        {jobs.length === 0 ? (
          <Text style={styles.emptyText}>No forecast jobs match this filter yet.</Text>
        ) : (
          jobs.map((job) => (
            <View key={job.id} style={styles.jobCard}>
              <View style={styles.jobHeader}>
                <View style={styles.jobTitleGroup}>
                  <Text style={styles.jobTitle}>{shortJobId(job.id)}</Text>
                  <Text style={styles.jobMeta}>
                    {job.latitude.toFixed(3)}, {job.longitude.toFixed(3)} / attempt {job.attempt}
                  </Text>
                </View>
                <Text style={[styles.statusBadge, statusBadgeStyle(job.status)]}>
                  {formatStatus(job.status)}
                </Text>
              </View>

              <Text numberOfLines={2} style={styles.jobMessage}>
                {job.error ?? job.diagnostics?.message ?? `Updated ${formatDateTime(job.updated_at)}`}
              </Text>

              <ForecastDiagnosticsSummary
                dense
                diagnostics={job.diagnostics}
                error={job.error}
                isFailed={job.status === "failed"}
              />

              <View style={styles.jobFooter}>
                <Text style={styles.footerText}>
                  {job.completed_at ? `Completed ${formatDateTime(job.completed_at)}` : "Active"}
                </Text>
                <View style={styles.actionRow}>
                  {canCancel(job.status) ? (
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => onCancelJob(job)}
                      style={({ pressed }) => [
                        styles.secondaryButton,
                        pressed && styles.buttonPressed,
                      ]}
                    >
                      <Text style={styles.secondaryButtonText}>Cancel</Text>
                    </Pressable>
                  ) : null}
                  {canRetry(job.status) ? (
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => onRetryJob(job)}
                      style={({ pressed }) => [
                        styles.primaryButton,
                        pressed && styles.buttonPressed,
                      ]}
                    >
                      <Text style={styles.primaryButtonText}>Retry</Text>
                    </Pressable>
                  ) : null}
                </View>
              </View>
            </View>
          ))
        )}
      </View>
    </View>
  );
}

function shortJobId(jobId: string) {
  return `Job ${jobId.slice(0, 8)}`;
}

function formatFilter(filter: JobHistoryFilter) {
  return filter === "all" ? "All" : formatStatus(filter);
}

function formatStatus(status: ForecastJobStatus) {
  const statusMap: Record<ForecastJobStatus, string> = {
    cancelled: "Cancelled",
    failed: "Failed",
    queued: "Queued",
    running: "Running",
    succeeded: "Succeeded",
  };

  return statusMap[status];
}

function canCancel(status: ForecastJobStatus) {
  return status === "queued" || status === "running";
}

function canRetry(status: ForecastJobStatus) {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}

function statusBadgeStyle(status: ForecastJobStatus) {
  if (status === "succeeded") {
    return styles.statusReady;
  }

  if (status === "failed" || status === "cancelled") {
    return styles.statusStopped;
  }

  return styles.statusActive;
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
  headerActions: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.sm,
  },
  refreshButton: {
    alignItems: "center",
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 34,
    justifyContent: "center",
    minWidth: 86,
    paddingHorizontal: spacing.sm,
  },
  refreshText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  filterRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  filterButton: {
    alignItems: "center",
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 34,
    minWidth: 86,
    justifyContent: "center",
    paddingHorizontal: spacing.sm,
  },
  filterButtonSelected: {
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
  },
  filterText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
  },
  filterTextSelected: {
    color: colors.text,
  },
  actionMessage: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0,
  },
  errorMessage: {
    color: colors.error,
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0,
  },
  jobList: {
    gap: spacing.sm,
  },
  emptyText: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
  },
  jobCard: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: spacing.sm,
    padding: spacing.sm,
  },
  jobHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    justifyContent: "space-between",
  },
  jobTitleGroup: {
    flex: 1,
    minWidth: 170,
  },
  jobTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800",
    letterSpacing: 0,
  },
  jobMeta: {
    color: colors.muted,
    fontSize: 12,
    letterSpacing: 0,
    marginTop: 2,
  },
  statusBadge: {
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
  statusActive: {
    backgroundColor: colors.badge,
  },
  statusReady: {
    backgroundColor: colors.accentSoft,
  },
  statusStopped: {
    backgroundColor: colors.errorSurface,
    color: colors.error,
  },
  jobMessage: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
  },
  jobFooter: {
    alignItems: "center",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    justifyContent: "space-between",
  },
  footerText: {
    color: colors.muted,
    flex: 1,
    fontSize: 12,
    letterSpacing: 0,
    minWidth: 150,
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
    minHeight: 34,
    justifyContent: "center",
    minWidth: 80,
    paddingHorizontal: spacing.sm,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  secondaryButton: {
    alignItems: "center",
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 34,
    justifyContent: "center",
    minWidth: 80,
    paddingHorizontal: spacing.sm,
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  buttonPressed: {
    opacity: 0.82,
  },
});
