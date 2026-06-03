import { formatConfidence } from "./forecastFormat";
import type { ForecastTimelineStep } from "../api/forecast";

export type RiskLevel = "low" | "moderate" | "elevated";

export const riskGroups = ["Outdoor", "Operations"] as const;

export type RiskGroup = (typeof riskGroups)[number];

export type RiskProfile = {
  maxHumidity: number;
  maxRain: number;
  maxTemperatureC: number;
  maxWind: number;
  minConfidence: number;
  minPressure: number;
};

export type RiskDecision = {
  action: string;
  driver: string;
  group: RiskGroup;
  id: string;
  label: string;
  level: RiskLevel;
  reason: string;
};

export type RiskDecisionSection = {
  decisions: RiskDecision[];
  group: RiskGroup;
};

export type RiskDecisionModel = {
  decisions: RiskDecision[];
  profile: RiskProfile;
  sections: RiskDecisionSection[];
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

export function buildRiskDecisionModel(
  timeline: ForecastTimelineStep[],
): RiskDecisionModel | null {
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

  return {
    decisions,
    profile,
    sections: riskGroups.map((group) => ({
      decisions: decisions.filter((decision) => decision.group === group),
      group,
    })),
  };
}

export function sortRiskDecisions(decisions: RiskDecision[]) {
  return [...decisions].sort((left, right) => {
    const rankDelta = riskLevelRank(right.level) - riskLevelRank(left.level);

    return rankDelta === 0 ? left.label.localeCompare(right.label) : rankDelta;
  });
}

export function riskLevelRank(level: RiskLevel) {
  if (level === "elevated") {
    return 2;
  }

  if (level === "moderate") {
    return 1;
  }

  return 0;
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
