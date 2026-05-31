This directory contains compact FourCastNet hosted-result fixtures for tests.

`hosted_point_sample.tar` keeps the hosted API member naming convention
(`000_000.npy`, `006_000.npy`, `012_000.npy`) and the point-sampling tensor
shape `(batch, variable, latitude, longitude)`, but uses a tiny 5x8 grid so the
fixture can be committed. Real hosted tar outputs are much larger and must stay
under local cache/data directories, not Git.
