import { StyleSheet, Text, View } from "react-native";

import { LocationPreset } from "../locations";
import { colors, spacing } from "../theme";

type ForecastHeroProps = {
  latitude: string;
  longitude: string;
  providerLabel: string;
  selectedPreset: LocationPreset | null;
};

export function ForecastHero({
  latitude,
  longitude,
  providerLabel,
  selectedPreset,
}: ForecastHeroProps) {
  return (
    <View style={styles.heroPanel}>
      <View style={styles.heroCopy}>
        <Text style={styles.heroLabel}>Forecast target</Text>
        <Text style={styles.heroTitle}>{selectedPreset?.label ?? "Custom point"}</Text>
        <Text style={styles.heroMeta}>
          {selectedPreset ? `${selectedPreset.region} / ` : ""}
          {latitude}, {longitude}
        </Text>
      </View>
      <View style={styles.heroBadge}>
        <Text style={styles.heroBadgeText}>{providerLabel}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  heroPanel: {
    backgroundColor: colors.hero,
    borderColor: colors.heroBorder,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 132,
    overflow: "hidden",
    padding: spacing.lg,
  },
  heroCopy: {
    flex: 1,
    gap: spacing.xs,
  },
  heroLabel: {
    color: colors.heroMuted,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  heroTitle: {
    color: colors.surface,
    fontSize: 30,
    fontWeight: "800",
    letterSpacing: 0,
  },
  heroMeta: {
    color: colors.heroMuted,
    fontSize: 14,
    letterSpacing: 0,
  },
  heroBadge: {
    alignItems: "center",
    alignSelf: "flex-start",
    backgroundColor: colors.badge,
    borderRadius: 8,
    minWidth: 64,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  heroBadgeText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
});
