import { StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme";
import { formatConfidence } from "../utils/forecastFormat";
import { buildRiskDecisionModel } from "../utils/riskDecisions";
import type { ForecastTimelineStep } from "../api/forecast";
import type { RiskDecision, RiskGroup, RiskLevel } from "../utils/riskDecisions";

type ForecastRiskDecisionPanelProps = {
  timeline: ForecastTimelineStep[];
};

export function ForecastRiskDecisionPanel({ timeline }: ForecastRiskDecisionPanelProps) {
  const model = buildRiskDecisionModel(timeline);

  if (!model) {
    return null;
  }

  return (
    <View style={styles.panel}>
      <View style={styles.header}>
        <Text style={styles.panelTitle}>Risk decisions</Text>
        <Text style={styles.headerMeta}>
          {formatConfidence(model.profile.minConfidence)} min confidence
        </Text>
      </View>
      {model.sections.map((section) => (
        <RiskSection
          decisions={section.decisions}
          key={section.group}
          title={section.group}
        />
      ))}
    </View>
  );
}

function RiskSection({
  decisions,
  title,
}: {
  decisions: RiskDecision[];
  title: RiskGroup;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <View style={styles.riskList}>
        {decisions.map((decision, index) => (
          <View
            key={decision.id}
            style={[
              styles.riskRow,
              index === decisions.length - 1 && styles.riskRowLast,
            ]}
          >
            <View style={styles.riskCopy}>
              <View style={styles.riskTitleRow}>
                <Text style={styles.riskName}>{decision.label}</Text>
                <Text style={[styles.levelBadge, levelBadgeStyle(decision.level)]}>
                  {decision.level}
                </Text>
              </View>
              <Text style={styles.driverText}>{decision.driver}</Text>
              <Text style={styles.reasonText}>{decision.reason}</Text>
              <Text style={styles.actionText}>{decision.action}</Text>
            </View>
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
  panel: {
    gap: spacing.md,
  },
  header: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
  },
  panelTitle: {
    color: colors.text,
    flex: 1,
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: 0,
  },
  headerMeta: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  riskList: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    overflow: "hidden",
  },
  riskRow: {
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    minHeight: 124,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  riskRowLast: {
    borderBottomWidth: 0,
  },
  riskCopy: {
    gap: spacing.xs,
  },
  riskTitleRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.sm,
    justifyContent: "space-between",
  },
  riskName: {
    color: colors.text,
    flex: 1,
    fontSize: 15,
    fontWeight: "900",
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
  driverText: {
    color: colors.hero,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0,
  },
  reasonText: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
  },
  actionText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0,
  },
});
