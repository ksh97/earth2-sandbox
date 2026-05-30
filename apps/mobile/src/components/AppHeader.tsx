import { StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme";

type AppHeaderProps = {
  hasError: boolean;
  syncState: string;
};

export function AppHeader({ hasError, syncState }: AppHeaderProps) {
  return (
    <View style={styles.header}>
      <Text style={styles.eyebrow}>Earth-2 Sandbox</Text>
      <View style={styles.headerRow}>
        <Text style={styles.title}>AI Weather</Text>
        <View style={styles.statusPill}>
          <View style={[styles.statusDot, hasError ? styles.statusDotError : null]} />
          <Text style={styles.statusText}>{syncState}</Text>
        </View>
      </View>
      <Text style={styles.subtitle}>FourCastNet-ready forecast workspace</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: spacing.xs,
    paddingTop: spacing.md,
  },
  headerRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.md,
    justifyContent: "space-between",
  },
  eyebrow: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  title: {
    color: colors.text,
    fontSize: 38,
    fontWeight: "800",
    letterSpacing: 0,
  },
  subtitle: {
    color: colors.muted,
    fontSize: 16,
    letterSpacing: 0,
  },
  statusPill: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.xs,
    minHeight: 34,
    paddingHorizontal: spacing.sm,
  },
  statusDot: {
    backgroundColor: colors.accent,
    borderRadius: 5,
    height: 10,
    width: 10,
  },
  statusDotError: {
    backgroundColor: colors.error,
  },
  statusText: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
});
