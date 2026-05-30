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
import { LocationPreset, locationPresets } from "./src/locations";
import { colors, spacing } from "./src/theme";

const initialLatitude = "37.5665";
const initialLongitude = "126.9780";
const initialPreset = locationPresets[0] ?? null;

export default function App() {
  const [latitude, setLatitude] = useState(initialLatitude);
  const [longitude, setLongitude] = useState(initialLongitude);
  const [selectedPreset, setSelectedPreset] = useState<LocationPreset | null>(initialPreset);
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

  const syncState = errorMessage ? "Offline" : isLoading ? "Syncing" : "Ready";

  async function refreshForecast(nextCoordinates?: { latitude: string; longitude: string }) {
    const requestLatitude = nextCoordinates?.latitude ?? latitude;
    const requestLongitude = nextCoordinates?.longitude ?? longitude;
    const parsedLatitude = Number(requestLatitude);
    const parsedLongitude = Number(requestLongitude);

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

  function choosePreset(preset: LocationPreset) {
    setSelectedPreset(preset);
    setLatitude(preset.latitude);
    setLongitude(preset.longitude);
    void refreshForecast({
      latitude: preset.latitude,
      longitude: preset.longitude,
    });
  }

  function updateLatitude(value: string) {
    setSelectedPreset(null);
    setLatitude(value);
  }

  function updateLongitude(value: string) {
    setSelectedPreset(null);
    setLongitude(value);
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
            <View style={styles.headerRow}>
              <Text style={styles.title}>AI Weather</Text>
              <View style={styles.statusPill}>
                <View style={[styles.statusDot, errorMessage ? styles.statusDotError : null]} />
                <Text style={styles.statusText}>{syncState}</Text>
              </View>
            </View>
            <Text style={styles.subtitle}>FourCastNet-ready forecast workspace</Text>
          </View>

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
              <Text style={styles.heroBadgeText}>Mock</Text>
            </View>
          </View>

          <View style={styles.panel}>
            <Text style={styles.panelTitle}>Location</Text>
            <View style={styles.presetRow}>
              {locationPresets.map((preset) => {
                const isSelected = selectedPreset?.label === preset.label;

                return (
                  <Pressable
                    accessibilityRole="button"
                    key={preset.label}
                    onPress={() => choosePreset(preset)}
                    style={({ pressed }) => [
                      styles.presetButton,
                      isSelected && styles.presetButtonSelected,
                      pressed && styles.buttonPressed,
                    ]}
                  >
                    <Text
                      style={[
                        styles.presetText,
                        isSelected && styles.presetTextSelected,
                      ]}
                    >
                      {preset.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            <View style={styles.inputRow}>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Latitude</Text>
                <TextInput
                  inputMode="decimal"
                  onChangeText={updateLatitude}
                  style={styles.input}
                  value={latitude}
                />
              </View>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Longitude</Text>
                <TextInput
                  inputMode="decimal"
                  onChangeText={updateLongitude}
                  style={styles.input}
                  value={longitude}
                />
              </View>
            </View>
            <Pressable
              accessibilityRole="button"
              disabled={isLoading}
              onPress={() => void refreshForecast()}
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
              <Text style={styles.panelTitle}>
                {selectedPreset?.label ?? "Custom forecast"}
              </Text>
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
                    <View style={styles.metricAccent} />
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
  presetRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  presetButton: {
    alignItems: "center",
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 38,
    minWidth: 94,
    justifyContent: "center",
    paddingHorizontal: spacing.sm,
  },
  presetButtonSelected: {
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
  },
  presetText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0,
  },
  presetTextSelected: {
    color: colors.text,
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
    overflow: "hidden",
    padding: spacing.md,
  },
  metricAccent: {
    backgroundColor: colors.accent,
    height: 4,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
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
