import { StyleSheet, Text, View } from "react-native";

import { ForecastJobDiagnostics } from "../api/forecast";
import { colors, spacing } from "../theme";

type ForecastDiagnosticsSummaryProps = {
  diagnostics: ForecastJobDiagnostics | null;
  error: string | null;
  isFailed: boolean;
  dense?: boolean;
};

type DiagnosticRow = {
  label: string;
  value: string;
};

export function ForecastDiagnosticsSummary({
  dense = false,
  diagnostics,
  error,
  isFailed,
}: ForecastDiagnosticsSummaryProps) {
  if (!isFailed) {
    return null;
  }

  const rows = buildDiagnosticRows(diagnostics);
  const message = formatDiagnosticMessage({ diagnostics, error, isFailed });

  return (
    <View style={[styles.section, dense && styles.sectionDense]}>
      <Text style={styles.title}>Failure diagnostics</Text>
      <Text numberOfLines={dense ? 2 : 4} style={styles.message}>
        {message}
      </Text>
      {rows.length > 0 ? (
        <View style={styles.rowGrid}>
          {rows.map((row) => (
            <View key={row.label} style={[styles.row, dense && styles.rowDense]}>
              <Text style={styles.rowLabel}>{row.label}</Text>
              <Text numberOfLines={2} style={styles.rowValue}>
                {row.value}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
      {isHostedProvider(diagnostics) ? (
        <Text style={styles.hint}>
          Retry the job after hosted output is available, or run the backend in mock mode to keep
          UI validation moving.
        </Text>
      ) : null}
    </View>
  );
}

function buildDiagnosticRows(diagnostics: ForecastJobDiagnostics | null): DiagnosticRow[] {
  if (!diagnostics) {
    return [];
  }

  return [
    optionalRow("Provider", diagnostics.provider),
    optionalRow("NVCF", diagnostics.nvcf_status),
    optionalRow("Source", diagnostics.response_source),
    optionalRow("Cache", diagnostics.cache_status),
    optionalRow("Reference", diagnostics.response_reference_present ? "Present" : "Missing"),
    optionalRow("Bytes", diagnostics.byte_length === null ? null : String(diagnostics.byte_length)),
    optionalRow("Polls", String(diagnostics.poll_attempts)),
    optionalRow("Request", shortRequestId(diagnostics.nvcf_request_id)),
  ].filter((row): row is DiagnosticRow => row !== null);
}

function optionalRow(label: string, value: string | null | undefined): DiagnosticRow | null {
  if (!value) {
    return null;
  }

  return { label, value };
}

function shortRequestId(requestId: string | null) {
  if (!requestId) {
    return null;
  }

  return requestId.slice(0, 8);
}

function formatDiagnosticMessage({
  diagnostics,
  error,
  isFailed,
}: {
  diagnostics: ForecastJobDiagnostics | null;
  error: string | null;
  isFailed: boolean;
}) {
  if (error) {
    return error;
  }

  if (diagnostics?.message) {
    return diagnostics.message;
  }

  if (isFailed) {
    return "The forecast job stopped before a usable forecast payload was produced.";
  }

  return "Provider metadata is available for this forecast job.";
}

function isHostedProvider(diagnostics: ForecastJobDiagnostics | null) {
  return diagnostics?.provider === "fourcastnet" || Boolean(diagnostics?.nvcf_status);
}

const styles = StyleSheet.create({
  section: {
    borderLeftColor: colors.error,
    borderLeftWidth: 3,
    gap: spacing.sm,
    paddingLeft: spacing.sm,
  },
  sectionDense: {
    gap: spacing.xs,
  },
  title: {
    color: colors.error,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  message: {
    color: colors.text,
    fontSize: 13,
    letterSpacing: 0,
  },
  rowGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  row: {
    minWidth: 96,
    paddingRight: spacing.sm,
  },
  rowDense: {
    minWidth: 82,
  },
  rowLabel: {
    color: colors.muted,
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0,
    textTransform: "uppercase",
  },
  rowValue: {
    color: colors.text,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0,
    marginTop: 2,
  },
  hint: {
    color: colors.muted,
    fontSize: 12,
    letterSpacing: 0,
  },
});
