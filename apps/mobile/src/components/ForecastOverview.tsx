import { StyleSheet, Text, View } from "react-native";

import { ForecastSummary } from "../api/forecast";
import { colors, spacing } from "../theme";
import { formatMetricName, formatUnit } from "../utils/forecastFormat";
import { ForecastRiskSummaryPanel } from "./ForecastRiskSummaryPanel";

type ForecastOverviewProps = {
  forecast: ForecastSummary;
};

export function ForecastOverview({ forecast }: ForecastOverviewProps) {
  return (
    <>
      <Text style={styles.headline}>{forecast.headline}</Text>
      <ForecastRiskSummaryPanel timeline={forecast.timeline} />
      <View style={styles.metricsGrid}>
        {forecast.metrics.map((metric) => (
          <View key={metric.name} style={styles.metricCard}>
            <View style={styles.metricAccent} />
            <Text style={styles.metricName}>{formatMetricName(metric.name)}</Text>
            <Text style={styles.metricValue}>
              {metric.value}
              <Text style={styles.metricUnit}> {formatUnit(metric.unit)}</Text>
            </Text>
          </View>
        ))}
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  headline: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "600",
    letterSpacing: 0,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metricCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexBasis: "31%",
    flexGrow: 1,
    minHeight: 108,
    minWidth: 104,
    overflow: "hidden",
    padding: spacing.md,
  },
  metricAccent: {
    backgroundColor: colors.accent,
    height: 4,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  metricName: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  metricValue: {
    color: colors.text,
    fontSize: 26,
    fontWeight: "800",
    letterSpacing: 0,
    marginTop: spacing.sm,
  },
  metricUnit: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: "700",
  },
});
