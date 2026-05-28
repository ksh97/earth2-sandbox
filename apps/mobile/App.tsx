import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { fetchSampleForecast, ForecastSummary } from "./src/api/forecast";
import { colors, spacing } from "./src/theme";

const initialLatitude = "37.5665";
const initialLongitude = "126.9780";

export default function App() {
  const [latitude, setLatitude] = useState(initialLatitude);
  const [longitude, setLongitude] = useState(initialLongitude);
  const [forecast, setForecast] = useState<ForecastSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const generatedAt = useMemo(() => {
    if (!forecast) {
      return "";
    }

    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(forecast.generated_at));
  }, [forecast]);

  async function refreshForecast() {
    const parsedLatitude = Number(latitude);
    const parsedLongitude = Number(longitude);

    if (!Number.isFinite(parsedLatitude) || !Number.isFinite(parsedLongitude)) {
      setErrorMessage("Enter numeric coordinates.");
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const nextForecast = await fetchSampleForecast({
        latitude: parsedLatitude,
        longitude: parsedLongitude,
      });
      setForecast(nextForecast);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Forecast request failed.";
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refreshForecast();
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />
      <KeyboardAvoidingView
        behavior={Platform.select({ ios: "padding", default: undefined })}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Text style={styles.eyebrow}>Earth-2 Sandbox</Text>
            <Text style={styles.title}>AI Weather</Text>
            <Text style={styles.subtitle}>FourCastNet-ready forecast client</Text>
          </View>

          <View style={styles.panel}>
            <Text style={styles.panelTitle}>Location</Text>
            <View style={styles.inputRow}>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Latitude</Text>
                <TextInput
                  inputMode="decimal"
                  onChangeText={setLatitude}
                  style={styles.input}
                  value={latitude}
                />
              </View>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Longitude</Text>
                <TextInput
                  inputMode="decimal"
                  onChangeText={setLongitude}
                  style={styles.input}
                  value={longitude}
                />
              </View>
            </View>
            <Pressable
              accessibilityRole="button"
              disabled={isLoading}
              onPress={refreshForecast}
              style={({ pressed }) => [
                styles.button,
                pressed && styles.buttonPressed,
                isLoading && styles.buttonDisabled,
              ]}
            >
              <Text style={styles.buttonText}>
                {isLoading ? "Updating forecast" : "Update forecast"}
              </Text>
            </Pressable>
          </View>

          {errorMessage ? (
            <View style={styles.errorPanel}>
              <Text style={styles.errorTitle}>Forecast unavailable</Text>
              <Text style={styles.errorText}>{errorMessage}</Text>
            </View>
          ) : null}

          <View style={styles.forecastPanel}>
            <View>
              <Text style={styles.panelTitle}>Seoul sample</Text>
              <Text style={styles.mutedText}>{generatedAt || "Waiting for forecast"}</Text>
            </View>
            {isLoading && !forecast ? (
              <ActivityIndicator color={colors.accent} />
            ) : (
              <Text style={styles.badge}>{forecast?.provider ?? "mock"}</Text>
            )}
          </View>

          {forecast ? (
            <>
              <Text style={styles.headline}>{forecast.headline}</Text>
              <View style={styles.metricsGrid}>
                {forecast.metrics.map((metric) => (
                  <View key={metric.name} style={styles.metricCard}>
                    <Text style={styles.metricName}>{formatMetricName(metric.name)}</Text>
                    <Text style={styles.metricValue}>
                      {metric.value}
                      <Text style={styles.metricUnit}> {formatUnit(metric.unit)}</Text>
                    </Text>
                  </View>
                ))}
              </View>
            </>
          ) : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function formatMetricName(name: string) {
  return name.replace(/_/g, " ");
}

function formatUnit(unit: string) {
  const unitMap: Record<string, string> = {
    celsius: "C",
    percent: "%",
  };

  return unitMap[unit] ?? unit;
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background,
  },
  keyboardView: {
    flex: 1,
  },
  container: {
    gap: spacing.lg,
    padding: spacing.lg,
    paddingBottom: spacing.xl,
  },
  header: {
    gap: spacing.xs,
    paddingTop: spacing.md,
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
  panel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: spacing.md,
    padding: spacing.md,
  },
  panelTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
    letterSpacing: 0,
  },
  inputRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  inputGroup: {
    flex: 1,
    gap: spacing.xs,
  },
  label: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  input: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text,
    fontSize: 16,
    minHeight: 48,
    paddingHorizontal: spacing.sm,
  },
  button: {
    alignItems: "center",
    backgroundColor: colors.accent,
    borderRadius: 8,
    minHeight: 48,
    justifyContent: "center",
    paddingHorizontal: spacing.md,
  },
  buttonPressed: {
    opacity: 0.82,
  },
  buttonDisabled: {
    opacity: 0.64,
  },
  buttonText: {
    color: colors.surface,
    fontSize: 16,
    fontWeight: "800",
    letterSpacing: 0,
  },
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
  forecastPanel: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 82,
    padding: spacing.md,
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
  headline: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "600",
    letterSpacing: 0,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  metricCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexBasis: "31%",
    flexGrow: 1,
    minHeight: 108,
    minWidth: 104,
    padding: spacing.md,
  },
  metricName: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  metricValue: {
    color: colors.text,
    fontSize: 26,
    fontWeight: "800",
    letterSpacing: 0,
    marginTop: spacing.sm,
  },
  metricUnit: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: "700",
  },
});
