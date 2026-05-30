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
  const level = status?.ready ? "Ready" : errorMessage ? "Offline" : "Checking";
  const detail = status?.detail ?? errorMessage ?? "Checking forecast provider status.";

  return (
    <View style={styles.panel}>
      <View style={styles.copy}>
        <Text style={styles.label}>Backend provider</Text>
        <Text style={styles.title}>{status ? formatProvider(status) : level}</Text>
        <Text style={styles.detail}>{detail}</Text>
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
  const support = status.supports_point_forecast ? "point ready" : "readiness only";
  return `${status.provider} / ${status.mode} / ${support}`;
}

const styles = StyleSheet.create({
  panel: {
    alignItems: "flex-start",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
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
