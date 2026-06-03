This directory contains compact FourCastNet hosted-result fixtures for tests.

`hosted_point_sample.tar` keeps the hosted API member naming convention
(`000_000.npy`, `006_000.npy`, `012_000.npy`) and the point-sampling tensor
shape `(batch, variable, latitude, longitude)`, but uses a tiny 5x8 grid so the
fixture can be committed. Real hosted tar outputs are much larger and must stay
under local cache/data directories, not Git.

`expected_metadata.json`, `expected_point_forecast_seoul.json`, and
`expected_point_forecast_tokyo.json` are golden outputs derived from the compact
tar fixture. They lock the decoder metadata, lead-time parsing, nearest-grid
sampling, Kelvin-to-Celsius conversion, Pa-to-hPa conversion, diagnostics-safe
forecast summary shape, and signal generation. Seoul and Tokyo currently map to
the same tiny fixture grid point; the separate golden files keep the location
contract explicit until larger real hosted samples are available locally.
