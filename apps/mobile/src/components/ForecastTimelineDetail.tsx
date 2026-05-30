import { StyleSheet, Text, View } from "react-native";

import { ForecastTimelineStep } from "../api/forecast";
import { colors, spacing } from "../theme";
import {
  formatCondition,
  formatConfidence,
  formatDateTime,
  formatLeadTime,
} from "../utils/forecastFormat";

type ForecastTimelineDetailProps = {
  step: ForecastTimelineStep;
};

export function ForecastTimelineDetail({ step }: ForecastTimelineDetailProps) {
  return (
    <View style={styles.timelineDetailPanel}>
      <View style={styles.detailHeader}>
        <View style={styles.detailHeaderCopy}>
          <Text style={styles.panelTitle}>{formatLeadTime(step.lead_time_hours)} detail</Text>
          <Text style={styles.mutedText}>{formatDateTime(step.valid_at)}</Text>
        </View>
        <Text style={styles.conditionBadge}>{formatCondition(step.condition)}</Text>
      </View>
      <Text style={styles.timelineSummary}>{step.summary}</Text>
      <View style={styles.detailMetricsGrid}>
        <DetailMetric label="Temperature" value={`${step.temperature_c} C`} />
        <DetailMetric label="Wind" value={`${step.wind_speed_ms} m/s`} />
        <DetailMetric label="Humidity" value={`${step.humidity_percent}%`} />
        <DetailMetric
          label="Rain chance"
          value={`${step.precipitation_probability_percent}%`}
        />
        <DetailMetric label="Pressure" value={`${step.pressure_hpa} hPa`} />
        <DetailMetric label="Confidence" value={formatConfidence(step.confidence)} />
      </View>
    </View>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailMetric}>
      <Text style={styles.detailMetricLabel}>{label}</Text>
      <Text style={styles.detailMetricValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  timelineDetailPanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: spacing.md,
    padding: spacing.md,
  },
  detailHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
  },
  detailHeaderCopy: {
    flex: 1,
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
  conditionBadge: {
    backgroundColor: colors.accentSoft,
    borderRadius: 8,
    color: colors.text,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    textTransform: "uppercase",
  },
  timelineSummary: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "600",
    letterSpacing: 0,
  },
  detailMetricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  detailMetric: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexBasis: "31%",
    flexGrow: 1,
    minHeight: 78,
    minWidth: 118,
    padding: spacing.sm,
  },
  detailMetricLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  detailMetricValue: {
    color: colors.text,
    fontSize: 19,
    fontWeight: "900",
    letterSpacing: 0,
    marginTop: spacing.xs,
  },
});
