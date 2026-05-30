import { StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme";

type ErrorPanelProps = {
  message: string;
};

export function ErrorPanel({ message }: ErrorPanelProps) {
  return (
    <View style={styles.errorPanel}>
      <Text style={styles.errorTitle}>Forecast unavailable</Text>
      <Text style={styles.errorText}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  errorPanel: {
    backgroundColor: colors.errorSurface,
    borderColor: colors.error,
    borderRadius: 8,
    borderWidth: 1,
    gap: spacing.xs,
    padding: spacing.md,
  },
  errorTitle: {
    color: colors.error,
    fontSize: 16,
    fontWeight: "800",
    letterSpacing: 0,
  },
  errorText: {
    color: colors.text,
    fontSize: 14,
    letterSpacing: 0,
  },
});
