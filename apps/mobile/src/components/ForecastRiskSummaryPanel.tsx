import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme";
import {
  buildRiskDecisionModel,
  riskGroups,
  sortRiskDecisions,
} from "../utils/riskDecisions";
import type { ForecastTimelineStep } from "../api/forecast";
import type { RiskGroup, RiskLevel } from "../utils/riskDecisions";

type ForecastRiskSummaryPanelProps = {
  timeline: ForecastTimelineStep[];
};

export function ForecastRiskSummaryPanel({ timeline }: ForecastRiskSummaryPanelProps) {
  const [selectedGroup, setSelectedGroup] = useState<RiskGroup>("Outdoor");
  const model = buildRiskDecisionModel(timeline);

  if (!model) {
    return null;
  }

  const selectedSection = model.sections.find((section) => section.group === selectedGroup);

  if (!selectedSection) {
    return null;
  }
  const sortedDecisions = sortRiskDecisions(selectedSection.decisions);
  const highestDecision = sortedDecisions[0];
  const visibleDecisions = sortedDecisions.slice(0, 3);

  return (
    <View style={styles.summaryPanel}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.panelTitle}>Decision watch</Text>
          <Text style={styles.mutedText}>{selectedSection.group} risk window</Text>
        </View>
        {highestDecision ? (
          <Text style={[styles.levelBadge, levelBadgeStyle(highestDecision.level)]}>
            {highestDecision.level}
          </Text>
        ) : null}
      </View>

      <View style={styles.segmentedControl}>
        {riskGroups.map((group) => {
          const isSelected = selectedGroup === group;

          return (
            <Pressable
              accessibilityRole="button"
              key={group}
              onPress={() => setSelectedGroup(group)}
              style={({ pressed }) => [
                styles.segmentButton,
                isSelected && styles.segmentButtonSelected,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={[styles.segmentText, isSelected && styles.segmentTextSelected]}>
                {group}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {highestDecision ? (
        <View style={styles.primaryDecision}>
          <Text style={styles.primaryLabel}>{highestDecision.label}</Text>
          <Text style={styles.primaryAction}>{highestDecision.action}</Text>
          <Text style={styles.primaryDriver}>{highestDecision.driver}</Text>
        </View>
      ) : null}

      <View style={styles.riskRows}>
        {visibleDecisions.map((decision, index) => (
          <View
            key={decision.id}
            style={[
              styles.riskRow,
              index === visibleDecisions.length - 1 && styles.riskRowLast,
            ]}
          >
            <View style={styles.riskCopy}>
              <Text style={styles.riskName}>{decision.label}</Text>
              <Text style={styles.riskReason}>{decision.reason}</Text>
            </View>
            <Text style={[styles.rowLevelBadge, levelBadgeStyle(decision.level)]}>
              {decision.level}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function levelBadgeStyle(level: RiskLevel) {
  if (level === "elevated") {
    return styles.levelElevated;
  }

  if (level === "moderate") {
    return styles.levelModerate;
  }

  return styles.levelLow;
}

const styles = StyleSheet.create({
  summaryPanel: {
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
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  segmentTextSelected: {
    color: colors.text,
  },
  buttonPressed: {
    opacity: 0.82,
  },
  primaryDecision: {
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    borderColor: colors.border,
    borderTopWidth: 1,
    gap: spacing.xs,
    paddingVertical: spacing.md,
  },
  primaryLabel: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "900",
    letterSpacing: 0,
  },
  primaryAction: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 0,
  },
  primaryDriver: {
    color: colors.hero,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0,
  },
  riskRows: {
    borderTopColor: colors.border,
    borderTopWidth: 1,
  },
  riskRow: {
    alignItems: "center",
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: spacing.md,
    minHeight: 68,
    paddingVertical: spacing.sm,
  },
  riskRowLast: {
    borderBottomWidth: 0,
  },
  riskCopy: {
    flex: 1,
    gap: 3,
  },
  riskName: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "900",
    letterSpacing: 0,
  },
  riskReason: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
  },
  levelBadge: {
    borderRadius: 8,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0,
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    textTransform: "uppercase",
  },
  rowLevelBadge: {
    borderRadius: 8,
    fontSize: 10,
    fontWeight: "900",
    letterSpacing: 0,
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    textTransform: "uppercase",
  },
  levelLow: {
    backgroundColor: colors.accentSoft,
    color: colors.text,
  },
  levelModerate: {
    backgroundColor: colors.badge,
    color: colors.text,
  },
  levelElevated: {
    backgroundColor: colors.errorSurface,
    color: colors.error,
  },
});
