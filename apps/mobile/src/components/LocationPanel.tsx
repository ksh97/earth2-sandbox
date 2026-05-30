import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { LocationPreset, locationPresets } from "../locations";
import { colors, spacing } from "../theme";

type LocationPanelProps = {
  isLoading: boolean;
  latitude: string;
  longitude: string;
  onChoosePreset: (preset: LocationPreset) => void;
  onRefresh: () => void;
  onUpdateLatitude: (value: string) => void;
  onUpdateLongitude: (value: string) => void;
  selectedPreset: LocationPreset | null;
};

export function LocationPanel({
  isLoading,
  latitude,
  longitude,
  onChoosePreset,
  onRefresh,
  onUpdateLatitude,
  onUpdateLongitude,
  selectedPreset,
}: LocationPanelProps) {
  return (
    <View style={styles.panel}>
      <Text style={styles.panelTitle}>Location</Text>
      <View style={styles.presetRow}>
        {locationPresets.map((preset) => {
          const isSelected = selectedPreset?.label === preset.label;

          return (
            <Pressable
              accessibilityRole="button"
              key={preset.label}
              onPress={() => onChoosePreset(preset)}
              style={({ pressed }) => [
                styles.presetButton,
                isSelected && styles.presetButtonSelected,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={[styles.presetText, isSelected && styles.presetTextSelected]}>
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
            onChangeText={onUpdateLatitude}
            style={styles.input}
            value={latitude}
          />
        </View>
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Longitude</Text>
          <TextInput
            inputMode="decimal"
            onChangeText={onUpdateLongitude}
            style={styles.input}
            value={longitude}
          />
        </View>
      </View>
      <Pressable
        accessibilityRole="button"
        disabled={isLoading}
        onPress={onRefresh}
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
  );
}

const styles = StyleSheet.create({
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
});
