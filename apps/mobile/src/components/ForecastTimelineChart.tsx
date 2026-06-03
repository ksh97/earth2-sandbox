import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme";
import { formatConfidence, formatLeadTime } from "../utils/forecastFormat";
import type { ForecastTimelineStep } from "../api/forecast";

type TimelineMetricKey = "temperature" | "wind" | "rain" | "confidence";

type ForecastTimelineChartProps = {
  onSelectLeadHour: (leadTimeHours: number) => void;
  selectedLeadTimeHours: number | null;
  timeline: ForecastTimelineStep[];
};

type TimelineMetricOption = {
  key: TimelineMetricKey;
  label: string;
  unitLabel: string;
};

const defaultMetricOption: TimelineMetricOption = {
  key: "temperature",
  label: "Temp",
  unitLabel: "C",
};

const metricOptions: TimelineMetricOption[] = [
  defaultMetricOption,
  { key: "wind", label: "Wind", unitLabel: "m/s" },
  { key: "rain", label: "Rain", unitLabel: "%" },
  { key: "confidence", label: "Conf", unitLabel: "%" },
];

export function ForecastTimelineChart({
  onSelectLeadHour,
  selectedLeadTimeHours,
  timeline,
}: ForecastTimelineChartProps) {
  const firstStep = timeline[0];
  const [selectedMetric, setSelectedMetric] = useState<TimelineMetricKey>("temperature");

  if (!firstStep) {
    return null;
  }

  const metric =
    metricOptions.find((option) => option.key === selectedMetric) ?? defaultMetricOption;
  const selectedStep =
    timeline.find((step) => step.lead_time_hours === selectedLeadTimeHours) ?? firstStep;
  const values = timeline.map((step) => getMetricValue(step, metric.key));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;
  const peakStep = timeline.reduce((currentPeak, step) =>
    getMetricValue(step, metric.key) > getMetricValue(currentPeak, metric.key)
      ? step
      : currentPeak,
  );

  return (
    <View style={styles.chartPanel}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.panelTitle}>Timeline chart</Text>
          <Text style={styles.mutedText}>
            Selected {formatLeadTime(selectedStep.lead_time_hours)} -{" "}
            {formatMetricValue(getMetricValue(selectedStep, metric.key), metric)}
          </Text>
        </View>
        <Text style={styles.peakBadge}>
          Peak {formatLeadTime(peakStep.lead_time_hours)}
        </Text>
      </View>

      <View style={styles.segmentedControl}>
        {metricOptions.map((option) => {
          const isSelected = selectedMetric === option.key;

          return (
            <Pressable
              accessibilityRole="button"
              key={option.key}
              onPress={() => setSelectedMetric(option.key)}
              style={({ pressed }) => [
                styles.segmentButton,
                isSelected && styles.segmentButtonSelected,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={[styles.segmentText, isSelected && styles.segmentTextSelected]}>
                {option.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.rangeRow}>
        <Text style={styles.rangeText}>{formatMetricValue(minValue, metric)} low</Text>
        <Text style={styles.rangeText}>{formatMetricValue(maxValue, metric)} high</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.chartRailContent}
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.chartRail}
      >
        {timeline.map((step) => {
          const value = getMetricValue(step, metric.key);
          const normalized = range === 0 ? 0.5 : (value - minValue) / range;
          const isSelected = step.lead_time_hours === selectedStep.lead_time_hours;
          const barHeight = 22 + normalized * 92;

          return (
            <Pressable
              accessibilityRole="button"
              key={step.lead_time_hours}
              onPress={() => onSelectLeadHour(step.lead_time_hours)}
              style={({ pressed }) => [
                styles.chartColumn,
                isSelected && styles.chartColumnSelected,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={styles.chartValue}>{formatMetricValue(value, metric)}</Text>
              <View style={styles.barTrack}>
                <View
                  style={[
                    styles.barFill,
                    { height: barHeight },
                    isSelected && styles.barFillSelected,
                  ]}
                />
              </View>
              <Text style={[styles.chartLead, isSelected && styles.chartLeadSelected]}>
                {formatLeadTime(step.lead_time_hours)}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

function getMetricValue(step: ForecastTimelineStep, metric: TimelineMetricKey) {
  if (metric === "temperature") {
    return step.temperature_c;
  }

  if (metric === "wind") {
    return step.wind_speed_ms;
  }

  if (metric === "rain") {
    return step.precipitation_probability_percent;
  }

  return step.confidence;
}

function formatMetricValue(value: number, metric: TimelineMetricOption) {
  if (metric.key === "confidence") {
    return formatConfidence(value);
  }

  if (metric.key === "wind") {
    return `${value.toFixed(1)} ${metric.unitLabel}`;
  }

  if (metric.key === "temperature") {
    return `${Math.round(value)} ${metric.unitLabel}`;
  }

  return `${Math.round(value)}${metric.unitLabel}`;
}

const styles = StyleSheet.create({
  chartPanel: {
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
    gap: spacing.md,
    justifyContent: "space-between",
  },
  headerCopy: {
    flex: 1,
  },
  panelTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "800",
    letterSpacing: 0,
  },
  mutedText: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
    marginTop: spacing.xs,
  },
  peakBadge: {
    backgroundColor: colors.badge,
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
  segmentedControl: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    padding: 4,
  },
  segmentButton: {
    alignItems: "center",
    borderRadius: 6,
    flex: 1,
    minHeight: 40,
    justifyContent: "center",
  },
  segmentButtonSelected: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
  },
  segmentText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  segmentTextSelected: {
    color: colors.text,
  },
  rangeRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  rangeText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  chartRail: {
    marginHorizontal: -spacing.md,
  },
  chartRailContent: {
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  chartColumn: {
    alignItems: "center",
    borderRadius: 8,
    gap: spacing.xs,
    justifyContent: "flex-end",
    minHeight: 178,
    minWidth: 78,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
  },
  chartColumnSelected: {
    backgroundColor: colors.input,
    borderColor: colors.hero,
    borderWidth: 1,
  },
  chartValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    minHeight: 18,
    textAlign: "center",
  },
  barTrack: {
    alignItems: "center",
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    height: 118,
    justifyContent: "flex-end",
    overflow: "hidden",
    width: 18,
  },
  barFill: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    minHeight: 8,
    width: 18,
  },
  barFillSelected: {
    backgroundColor: colors.hero,
  },
  chartLead: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
  },
  chartLeadSelected: {
    color: colors.text,
  },
  buttonPressed: {
    opacity: 0.82,
  },
});
