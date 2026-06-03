import { StyleSheet, Text, View } from "react-native";

import { ForecastTimelineStep } from "../api/forecast";
import { colors, spacing } from "../theme";
import { formatConfidence } from "../utils/forecastFormat";

type RiskLevel = "low" | "moderate" | "elevated";
type RiskGroup = "Outdoor" | "Operations";

type ForecastRiskDecisionPanelProps = {
  timeline: ForecastTimelineStep[];
};

type RiskProfile = {
  maxHumidity: number;
  maxRain: number;
  maxTemperatureC: number;
  maxWind: number;
  minConfidence: number;
  minPressure: number;
};

type RiskDecision = {
  action: string;
  driver: string;
  group: RiskGroup;
  id: string;
  label: string;
  level: RiskLevel;
  reason: string;
};

type RiskRule = {
  action: Record<RiskLevel, string>;
  driver: (profile: RiskProfile) => string;
  group: RiskGroup;
  id: string;
  label: string;
  level: (profile: RiskProfile) => RiskLevel;
  reason: (profile: RiskProfile) => string;
};

const riskRules: RiskRule[] = [
  {
    action: {
      elevated: "Delay exposed ridge routes or move to a sheltered window.",
      low: "Proceed with normal route checks.",
      moderate: "Keep a shorter route option and monitor wind shifts.",
    },
    driver: (profile) => `${formatPercent(profile.maxRain)} rain, ${formatWind(profile.maxWind)}`,
    group: "Outdoor",
    id: "hiking",
    label: "Hiking",
    level: (profile) =>
      levelFromFlags({
        elevated: [
          profile.maxRain >= 60,
          profile.maxWind >= 12,
          profile.minConfidence < 0.68,
          profile.maxTemperatureC >= 34,
        ],
        moderate: [
          profile.maxRain >= 40,
          profile.maxWind >= 8,
          profile.minConfidence < 0.78,
          profile.maxTemperatureC >= 31,
        ],
      }),
    reason: (profile) =>
      `Peak rain ${formatPercent(profile.maxRain)} with wind up to ${formatWind(
        profile.maxWind,
      )}.`,
  },
  {
    action: {
      elevated: "Use a hard shelter plan and avoid exposed overnight setup.",
      low: "Standard campsite setup is enough.",
      moderate: "Pack extra anchoring and keep drainage in mind.",
    },
    driver: (profile) =>
      `${formatPercent(profile.maxRain)} rain, ${formatPercent(profile.maxHumidity)} humidity`,
    group: "Outdoor",
    id: "camping",
    label: "Camping",
    level: (profile) =>
      levelFromFlags({
        elevated: [profile.maxRain >= 55, profile.maxWind >= 10, profile.maxHumidity >= 90],
        moderate: [profile.maxRain >= 35, profile.maxWind >= 7, profile.maxHumidity >= 80],
      }),
    reason: (profile) =>
      `Rain reaches ${formatPercent(profile.maxRain)} and humidity peaks at ${formatPercent(
        profile.maxHumidity,
      )}.`,
  },
  {
    action: {
      elevated: "Avoid small-boat windows and keep shoreline plans flexible.",
      low: "Proceed with normal water checks.",
      moderate: "Favor protected water and confirm local wind before launch.",
    },
    driver: (profile) => `${formatWind(profile.maxWind)}, ${formatPressure(profile.minPressure)}`,
    group: "Outdoor",
    id: "fishing",
    label: "Fishing",
    level: (profile) =>
      levelFromFlags({
        elevated: [profile.maxWind >= 9, profile.maxRain >= 55, profile.minPressure < 1002],
        moderate: [profile.maxWind >= 6, profile.maxRain >= 35, profile.minPressure < 1007],
      }),
    reason: (profile) =>
      `Wind tops ${formatWind(profile.maxWind)} with pressure floor at ${formatPressure(
        profile.minPressure,
      )}.`,
  },
  {
    action: {
      elevated: "Do not schedule flight until wind and rain risk drops.",
      low: "Flight window looks usable with standard site checks.",
      moderate: "Keep flights short and verify gusts at the launch site.",
    },
    driver: (profile) =>
      `${formatWind(profile.maxWind)}, ${formatPercent(profile.maxRain)} rain`,
    group: "Outdoor",
    id: "drone",
    label: "Drone filming",
    level: (profile) =>
      levelFromFlags({
        elevated: [profile.maxWind >= 8, profile.maxRain >= 35, profile.minConfidence < 0.72],
        moderate: [profile.maxWind >= 5.5, profile.maxRain >= 20, profile.minConfidence < 0.8],
      }),
    reason: (profile) =>
      `Wind peaks at ${formatWind(profile.maxWind)} and minimum confidence is ${formatConfidence(
        profile.minConfidence,
      )}.`,
  },
  {
    action: {
      elevated: "Pre-stage delay buffers and review exposed route segments.",
      low: "Run standard dispatch monitoring.",
      moderate: "Add slack for route timing and loading windows.",
    },
    driver: (profile) => `${formatPercent(profile.maxRain)} rain, ${formatWind(profile.maxWind)}`,
    group: "Operations",
    id: "logistics",
    label: "Logistics",
    level: (profile) =>
      levelFromFlags({
        elevated: [profile.maxRain >= 65, profile.maxWind >= 13, profile.minConfidence < 0.68],
        moderate: [profile.maxRain >= 45, profile.maxWind >= 9, profile.minConfidence < 0.78],
      }),
    reason: (profile) =>
      `Operational window sees ${formatPercent(profile.maxRain)} rain risk and ${formatWind(
        profile.maxWind,
      )} wind.`,
  },
  {
    action: {
      elevated: "Prepare escalation coverage for wind and pressure-sensitive assets.",
      low: "Keep routine load and site monitoring.",
      moderate: "Watch wind ramps and pressure-sensitive operations.",
    },
    driver: (profile) => `${formatWind(profile.maxWind)}, ${formatPressure(profile.minPressure)}`,
    group: "Operations",
    id: "energy",
    label: "Energy sites",
    level: (profile) =>
      levelFromFlags({
        elevated: [profile.maxWind >= 14, profile.minPressure < 1002, profile.minConfidence < 0.68],
        moderate: [profile.maxWind >= 10, profile.minPressure < 1007, profile.minConfidence < 0.78],
      }),
    reason: (profile) =>
      `Wind reaches ${formatWind(profile.maxWind)} and pressure drops to ${formatPressure(
        profile.minPressure,
      )}.`,
  },
  {
    action: {
      elevated: "Protect field work from soil saturation and heat stress windows.",
      low: "Proceed with normal field monitoring.",
      moderate: "Schedule sensitive field work around wet or hot periods.",
    },
    driver: (profile) =>
      `${formatPercent(profile.maxRain)} rain, ${formatTemperature(profile.maxTemperatureC)}`,
    group: "Operations",
    id: "agriculture",
    label: "Agriculture",
    level: (profile) =>
      levelFromFlags({
        elevated: [profile.maxRain >= 60, profile.maxHumidity >= 92, profile.maxTemperatureC >= 34],
        moderate: [profile.maxRain >= 40, profile.maxHumidity >= 82, profile.maxTemperatureC >= 30],
      }),
    reason: (profile) =>
      `Rain peaks at ${formatPercent(profile.maxRain)} with ${formatTemperature(
        profile.maxTemperatureC,
      )} heat ceiling.`,
  },
  {
    action: {
      elevated: "Pause lift, roof, and exposed exterior work windows.",
      low: "Continue standard site safety checks.",
      moderate: "Review lift plans and exterior work timing.",
    },
    driver: (profile) => `${formatWind(profile.maxWind)}, ${formatPercent(profile.maxRain)} rain`,
    group: "Operations",
    id: "construction",
    label: "Construction",
    level: (profile) =>
      levelFromFlags({
        elevated: [profile.maxWind >= 12, profile.maxRain >= 55, profile.minConfidence < 0.68],
        moderate: [profile.maxWind >= 8, profile.maxRain >= 35, profile.minConfidence < 0.78],
      }),
    reason: (profile) =>
      `Wind tops ${formatWind(profile.maxWind)} and rain chance reaches ${formatPercent(
        profile.maxRain,
      )}.`,
  },
];

export function ForecastRiskDecisionPanel({ timeline }: ForecastRiskDecisionPanelProps) {
  if (timeline.length === 0) {
    return null;
  }

  const profile = buildRiskProfile(timeline);
  const decisions = riskRules.map((rule) => {
    const level = rule.level(profile);

    return {
      action: rule.action[level],
      driver: rule.driver(profile),
      group: rule.group,
      id: rule.id,
      label: rule.label,
      level,
      reason: rule.reason(profile),
    };
  });

  const outdoorDecisions = decisions.filter((decision) => decision.group === "Outdoor");
  const operationsDecisions = decisions.filter((decision) => decision.group === "Operations");

  return (
    <View style={styles.panel}>
      <View style={styles.header}>
        <Text style={styles.panelTitle}>Risk decisions</Text>
        <Text style={styles.headerMeta}>
          {formatConfidence(profile.minConfidence)} min confidence
        </Text>
      </View>
      <RiskSection decisions={outdoorDecisions} title="Outdoor" />
      <RiskSection decisions={operationsDecisions} title="Operations" />
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

function buildRiskProfile(timeline: ForecastTimelineStep[]): RiskProfile {
  return {
    maxHumidity: maxOf(timeline, (step) => step.humidity_percent),
    maxRain: maxOf(timeline, (step) => step.precipitation_probability_percent),
    maxTemperatureC: maxOf(timeline, (step) => step.temperature_c),
    maxWind: maxOf(timeline, (step) => step.wind_speed_ms),
    minConfidence: minOf(timeline, (step) => step.confidence),
    minPressure: minOf(timeline, (step) => step.pressure_hpa),
  };
}

function levelFromFlags({
  elevated,
  moderate,
}: {
  elevated: boolean[];
  moderate: boolean[];
}): RiskLevel {
  const elevatedCount = elevated.filter(Boolean).length;
  const moderateCount = moderate.filter(Boolean).length;

  if (elevatedCount > 0 || moderateCount >= 2) {
    return "elevated";
  }

  if (moderateCount === 1) {
    return "moderate";
  }

  return "low";
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

function maxOf(
  timeline: ForecastTimelineStep[],
  selector: (step: ForecastTimelineStep) => number,
) {
  return Math.max(...timeline.map(selector));
}

function minOf(
  timeline: ForecastTimelineStep[],
  selector: (step: ForecastTimelineStep) => number,
) {
  return Math.min(...timeline.map(selector));
}

function formatPercent(value: number) {
  return `${Math.round(value)}%`;
}

function formatPressure(value: number) {
  return `${Math.round(value)} hPa`;
}

function formatTemperature(value: number) {
  return `${Math.round(value)} C`;
}

function formatWind(value: number) {
  return `${value.toFixed(1)} m/s`;
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
