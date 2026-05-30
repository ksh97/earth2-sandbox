import { ActivityIndicator, StyleSheet, Text, View } from "react-native";

import { ForecastSummary } from "../api/forecast";
import { LocationPreset } from "../locations";
import { colors, spacing } from "../theme";

type ForecastStatusPanelProps = {
  forecast: ForecastSummary | null;
  generatedAt: string;
  isLoading: boolean;
  selectedPreset: LocationPreset | null;
};

export function ForecastStatusPanel({
  forecast,
  generatedAt,
  isLoading,
  selectedPreset,
}: ForecastStatusPanelProps) {
  return (
    <View style={styles.forecastPanel}>
      <View>
        <Text style={styles.panelTitle}>{selectedPreset?.label ?? "Custom forecast"}</Text>
        <Text style={styles.mutedText}>{generatedAt || "Waiting for forecast"}</Text>
      </View>
      {isLoading && !forecast ? (
        <ActivityIndicator color={colors.accent} />
      ) : (
        <Text style={styles.badge}>{forecast?.provider ?? "mock"}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  forecastPanel: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 82,
    padding: spacing.md,
  },
  panelTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: 0,
  },
  mutedText: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
    marginTop: spacing.xs,
  },
  badge: {
    backgroundColor: colors.badge,
    borderRadius: 8,
    color: colors.text,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0,
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    textTransform: "uppercase",
  },
});
