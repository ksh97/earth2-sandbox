import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { ForecastSummary, ForecastTimelineStep } from "../api/forecast";
import { colors, spacing } from "../theme";
import { formatCondition, formatLeadTime } from "../utils/forecastFormat";
import { ForecastRiskDecisionPanel } from "./ForecastRiskDecisionPanel";
import { ForecastSignalList } from "./ForecastSignalList";
import { ForecastTimelineDetail } from "./ForecastTimelineDetail";

type ForecastDetailsProps = {
  forecast: ForecastSummary;
  forecastWindowEnd: string;
  onSelectLeadHour: (leadTimeHours: number) => void;
  selectedTimelineStep: ForecastTimelineStep | null;
  timeline: ForecastTimelineStep[];
};

export function ForecastDetails({
  forecast,
  forecastWindowEnd,
  onSelectLeadHour,
  selectedTimelineStep,
  timeline,
}: ForecastDetailsProps) {
  return (
    <>
      <View style={styles.detailPanel}>
        <View style={styles.detailHeader}>
          <View style={styles.detailHeaderCopy}>
            <Text style={styles.panelTitle}>Forecast detail</Text>
            <Text style={styles.mutedText}>{forecast.model.name}</Text>
          </View>
          <Text style={styles.badge}>{forecast.model.run_mode}</Text>
        </View>
        <View style={styles.detailRows}>
          <DetailRow label="Resolution" value={forecast.model.resolution} />
          <DetailRow label="Forecast window" value={`Until ${forecastWindowEnd}`} />
          <DetailRow label="Step" value={`Every ${forecast.forecast_window.step_hours}h`} />
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.timelineRailContent}
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.timelineRail}
      >
        {timeline.map((step) => {
          const isSelected = selectedTimelineStep?.lead_time_hours === step.lead_time_hours;

          return (
            <Pressable
              accessibilityRole="button"
              key={step.lead_time_hours}
              onPress={() => onSelectLeadHour(step.lead_time_hours)}
              style={({ pressed }) => [
                styles.timelineChip,
                isSelected && styles.timelineChipSelected,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={[styles.timelineLead, isSelected && styles.timelineTextSelected]}>
                {formatLeadTime(step.lead_time_hours)}
              </Text>
              <Text
                style={[styles.timelineCondition, isSelected && styles.timelineTextSelected]}
              >
                {formatCondition(step.condition)}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>

      {selectedTimelineStep ? (
        <ForecastTimelineDetail step={selectedTimelineStep} />
      ) : null}

      <ForecastRiskDecisionPanel timeline={timeline} />

      <ForecastSignalList signals={forecast.signals} />
    </>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  detailPanel: {
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
  detailRows: {
    borderTopColor: colors.border,
    borderTopWidth: 1,
  },
  detailRow: {
    alignItems: "center",
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
    minHeight: 44,
  },
  detailLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  detailValue: {
    color: colors.text,
    flex: 1,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 0,
    textAlign: "right",
  },
  timelineRail: {
    marginHorizontal: -spacing.lg,
  },
  timelineRailContent: {
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  timelineChip: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: 2,
    minHeight: 68,
    minWidth: 98,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
  },
  timelineChipSelected: {
    backgroundColor: colors.hero,
    borderColor: colors.heroBorder,
  },
  timelineLead: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "900",
    letterSpacing: 0,
  },
  timelineCondition: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0,
  },
  timelineTextSelected: {
    color: colors.surface,
  },
  buttonPressed: {
    opacity: 0.82,
  },
});
