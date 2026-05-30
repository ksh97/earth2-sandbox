export function formatScreenMode(mode: "overview" | "details") {
  return mode === "overview" ? "Overview" : "Details";
}

export function formatMetricName(name: string) {
  return name.replace(/_/g, " ");
}

export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatLeadTime(leadTimeHours: number) {
  return leadTimeHours === 0 ? "Now" : `+${leadTimeHours}h`;
}

export function formatCondition(condition: string) {
  const conditionMap: Record<string, string> = {
    breezy: "Breezy",
    clear: "Clear",
    humid: "Humid",
    rain_watch: "Rain watch",
  };

  return conditionMap[condition] ?? condition;
}

export function formatConfidence(confidence: number) {
  return `${Math.round(confidence * 100)}%`;
}

export function formatUnit(unit: string) {
  const unitMap: Record<string, string> = {
    celsius: "C",
    percent: "%",
  };

  return unitMap[unit] ?? unit;
}
