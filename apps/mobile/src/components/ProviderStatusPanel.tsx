import { Pressable, StyleSheet, Text, View } from "react-native";

import { ForecastProviderStatus } from "../api/forecast";
import { colors, spacing } from "../theme";

type ProviderStatusPanelProps = {
  errorMessage: string | null;
  onRefresh: () => void;
  status: ForecastProviderStatus | null;
};

export function ProviderStatusPanel({
  errorMessage,
  onRefresh,
  status,
}: ProviderStatusPanelProps) {
  const level = status ? formatStatusLevel(status) : errorMessage ? "Offline" : "Checking";
  const detail = status?.detail ?? errorMessage ?? "Checking forecast provider status.";

  return (
    <View style={styles.panel}>
      <View style={styles.copy}>
        <Text style={styles.label}>Backend provider</Text>
        <Text style={styles.title}>{status ? formatProvider(status) : level}</Text>
        <Text style={styles.detail}>{detail}</Text>
        {status ? (
          <View style={styles.metaGrid}>
            <StatusMeta label="Configured" value={status.configured ? "Yes" : "No"} />
            <StatusMeta
              label="Output"
              value={formatOutputState(status)}
            />
            <StatusMeta label="Endpoint" value={status.endpoint ?? "local mock"} />
          </View>
        ) : null}
      </View>
      <View style={styles.actions}>
        <Text
          style={[
            styles.badge,
            status?.ready ? styles.badgeReady : errorMessage ? styles.badgeOffline : null,
          ]}
        >
          {level}
        </Text>
        <Pressable
          accessibilityRole="button"
          onPress={onRefresh}
          style={({ pressed }) => [styles.refreshButton, pressed && styles.buttonPressed]}
        >
          <Text style={styles.refreshText}>Refresh</Text>
        </Pressable>
      </View>
    </View>
  );
}

function formatProvider(status: ForecastProviderStatus) {
  const support =
    status.provider === "fourcastnet" && status.supports_point_forecast
      ? "output unverified"
      : status.supports_point_forecast
        ? "point ready"
        : "readiness only";
  return `${status.provider} / ${status.mode} / ${support}`;
}

function formatStatusLevel(status: ForecastProviderStatus) {
  if (!status.ready) {
    return "Blocked";
  }

  if (status.provider === "fourcastnet") {
    return status.supports_point_forecast ? "Configured" : "Readiness";
  }

  return "Ready";
}

function formatOutputState(status: ForecastProviderStatus) {
  if (!status.supports_point_forecast) {
    return "Blocked";
  }

  return status.provider === "fourcastnet" ? "Verify by job" : "Ready";
}

function StatusMeta({ label, value }: { label: string; value: string }) {
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
    alignItems: "flex-start",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    justifyContent: "space-between",
    padding: spacing.md,
  },
  copy: {
    flex: 1,
    gap: spacing.xs,
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
    fontSize: 16,
    fontWeight: "800",
    letterSpacing: 0,
  },
  detail: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
  },
  metaGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  metaItem: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexGrow: 1,
    minWidth: 140,
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
  actions: {
    alignItems: "flex-end",
    gap: spacing.sm,
  },
  badge: {
    backgroundColor: colors.input,
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
  badgeReady: {
    backgroundColor: colors.accentSoft,
  },
  badgeOffline: {
    backgroundColor: colors.errorSurface,
    color: colors.error,
  },
  refreshButton: {
    alignItems: "center",
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 34,
    justifyContent: "center",
    paddingHorizontal: spacing.sm,
  },
  refreshText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  buttonPressed: {
    opacity: 0.82,
  },
});
