import { StyleSheet, Text, View } from "react-native";

import { ForecastSignal } from "../api/forecast";
import { colors, spacing } from "../theme";

type ForecastSignalListProps = {
  signals: ForecastSignal[];
};

export function ForecastSignalList({ signals }: ForecastSignalListProps) {
  return (
    <View style={styles.signalList}>
      {signals.map((signal) => (
        <View key={signal.name} style={styles.signalRow}>
          <View style={styles.signalCopy}>
            <Text style={styles.signalName}>{signal.name}</Text>
            <Text style={styles.signalMessage}>{signal.message}</Text>
          </View>
          <Text style={[styles.signalLevel, signalLevelStyle(signal.level)]}>
            {signal.level}
          </Text>
        </View>
      ))}
    </View>
  );
}

function signalLevelStyle(level: "low" | "moderate" | "elevated") {
  if (level === "elevated") {
    return styles.signalLevelElevated;
  }

  if (level === "moderate") {
    return styles.signalLevelModerate;
  }

  return styles.signalLevelLow;
}

const styles = StyleSheet.create({
  signalList: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
  },
  signalRow: {
    alignItems: "center",
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
    minHeight: 74,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  signalCopy: {
    flex: 1,
    gap: 3,
  },
  signalName: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "800",
    letterSpacing: 0,
  },
  signalMessage: {
    color: colors.muted,
    fontSize: 13,
    letterSpacing: 0,
  },
  signalLevel: {
    borderRadius: 8,
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 0,
    overflow: "hidden",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    textTransform: "uppercase",
  },
  signalLevelLow: {
    backgroundColor: colors.accentSoft,
    color: colors.text,
  },
  signalLevelModerate: {
    backgroundColor: colors.badge,
    color: colors.text,
  },
  signalLevelElevated: {
    backgroundColor: colors.errorSurface,
    color: colors.error,
  },
});
