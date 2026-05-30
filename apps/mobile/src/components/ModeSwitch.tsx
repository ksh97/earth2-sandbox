import { Pressable, StyleSheet, Text, View } from "react-native";

import { ScreenMode, screenModes } from "../hooks/useForecast";
import { colors } from "../theme";
import { formatScreenMode } from "../utils/forecastFormat";

type ModeSwitchProps = {
  onChange: (mode: ScreenMode) => void;
  value: ScreenMode;
};

export function ModeSwitch({ onChange, value }: ModeSwitchProps) {
  return (
    <View style={styles.segmentedControl}>
      {screenModes.map((mode) => {
        const isSelected = value === mode;

        return (
          <Pressable
            accessibilityRole="button"
            key={mode}
            onPress={() => onChange(mode)}
            style={({ pressed }) => [
              styles.segmentButton,
              isSelected && styles.segmentButtonSelected,
              pressed && styles.buttonPressed,
            ]}
          >
            <Text style={[styles.segmentText, isSelected && styles.segmentTextSelected]}>
              {formatScreenMode(mode)}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  segmentedControl: {
    backgroundColor: colors.input,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    padding: 4,
  },
  segmentButton: {
    alignItems: "center",
    borderRadius: 6,
    flex: 1,
    minHeight: 40,
    justifyContent: "center",
  },
  segmentButtonSelected: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
  },
  segmentText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  segmentTextSelected: {
    color: colors.text,
  },
  buttonPressed: {
    opacity: 0.82,
  },
});
