import {
  KeyboardAvoidingView,
  Platform,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
} from "react-native";

import { AppHeader } from "../components/AppHeader";
import { ErrorPanel } from "../components/ErrorPanel";
import { ForecastDetails } from "../components/ForecastDetails";
import { ForecastHero } from "../components/ForecastHero";
import { ForecastHistoryPanel } from "../components/ForecastHistoryPanel";
import { ForecastJobPanel } from "../components/ForecastJobPanel";
import { ForecastOverview } from "../components/ForecastOverview";
import { ForecastStatusPanel } from "../components/ForecastStatusPanel";
import { LocationPanel } from "../components/LocationPanel";
import { ModeSwitch } from "../components/ModeSwitch";
import { ProviderStatusPanel } from "../components/ProviderStatusPanel";
import { useForecast } from "../hooks/useForecast";
import { colors, spacing } from "../theme";
import { SettingsDebugScreen } from "./SettingsDebugScreen";

export function ForecastScreen() {
  const {
    cancelJob,
    choosePreset,
    errorMessage,
    forecast,
    forecastJob,
    forecastJobPoll,
    forecastWindowEnd,
    generatedAt,
    isJobHistoryLoading,
    isJobPolling,
    isLoading,
    jobActionMessage,
    jobHistory,
    jobHistoryErrorMessage,
    jobHistoryFilter,
    latitude,
    longitude,
    providerErrorMessage,
    providerStatus,
    refreshJobHistory,
    refreshForecast,
    refreshProviderStatus,
    retryJob,
    screenMode,
    selectedPreset,
    selectedTimelineStep,
    setScreenMode,
    setSelectedLeadHour,
    syncState,
    timeline,
    updateLatitude,
    updateLongitude,
    updateJobHistoryFilter,
  } = useForecast();

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="dark-content" />
      <KeyboardAvoidingView
        behavior={Platform.select({ ios: "padding", default: undefined })}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <AppHeader hasError={Boolean(errorMessage)} syncState={syncState} />
          <ForecastHero
            latitude={latitude}
            longitude={longitude}
            providerLabel={providerStatus?.provider ?? forecast?.provider ?? "Mock"}
            selectedPreset={selectedPreset}
          />
          <ProviderStatusPanel
            errorMessage={providerErrorMessage}
            onRefresh={() => void refreshProviderStatus()}
            status={providerStatus}
          />
          <LocationPanel
            isLoading={isLoading}
            latitude={latitude}
            longitude={longitude}
            onChoosePreset={choosePreset}
            onRefresh={() => void refreshForecast()}
            onUpdateLatitude={updateLatitude}
            onUpdateLongitude={updateLongitude}
            selectedPreset={selectedPreset}
          />

          {errorMessage ? <ErrorPanel message={errorMessage} /> : null}

          <ForecastJobPanel
            isPolling={isJobPolling}
            job={forecastJob}
            onCancelJob={cancelJob}
            onRetryJob={retryJob}
            poll={forecastJobPoll}
          />
          <ForecastHistoryPanel
            actionMessage={jobActionMessage}
            errorMessage={jobHistoryErrorMessage}
            filter={jobHistoryFilter}
            isLoading={isJobHistoryLoading}
            jobs={jobHistory}
            onCancelJob={cancelJob}
            onChangeFilter={updateJobHistoryFilter}
            onRefresh={() => void refreshJobHistory()}
            onRetryJob={retryJob}
          />

          <ForecastStatusPanel
            forecast={forecast}
            generatedAt={generatedAt}
            isLoading={isLoading}
            selectedPreset={selectedPreset}
          />

          {forecast ? (
            <>
              <ModeSwitch onChange={setScreenMode} value={screenMode} />
              {screenMode === "overview" ? (
                <ForecastOverview forecast={forecast} />
              ) : (
                <ForecastDetails
                  forecast={forecast}
                  forecastWindowEnd={forecastWindowEnd}
                  onSelectLeadHour={setSelectedLeadHour}
                  selectedTimelineStep={selectedTimelineStep}
                  timeline={timeline}
                />
              )}
            </>
          ) : null}

          <SettingsDebugScreen
            currentJob={forecastJob}
            providerErrorMessage={providerErrorMessage}
            providerStatus={providerStatus}
            recentJobs={jobHistory}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
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
});
