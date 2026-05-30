import tarfile
from io import BytesIO

import numpy as np

from earth2_sandbox.postprocessing import FourCastNetPostProcessor


def test_fourcastnet_tar_decoder_reads_nvidia_naming_convention() -> None:
    processor = FourCastNetPostProcessor()
    content = build_tar_bytes(
        {
            "000_000.npy": np.array([[[[1.0, 2.0], [3.0, 4.0]]]], dtype=np.float32),
            "006_000.npy": np.array([[[[5.0, 6.0], [7.0, 8.0]]]], dtype=np.float32),
            "012_000.npy": b"not a numpy array",
            "notes.txt": b"ignored",
        }
    )

    summary = processor.decode_tar_bytes(content)

    assert summary.member_count == 2
    assert summary.lead_time_hours == [0, 6]
    assert summary.batch_indices == [0]
    assert summary.warnings[0].startswith("Could not load NumPy array from 012_000.npy")
    assert summary.warnings[1] == "Skipping unsupported tar member name: notes.txt"
    assert summary.arrays[0].filename == "000_000.npy"
    assert summary.arrays[0].shape == [1, 1, 2, 2]
    assert summary.arrays[0].dtype == "float32"
    assert summary.arrays[0].finite_count == 4
    assert summary.arrays[0].min_value == 1.0
    assert summary.arrays[0].max_value == 4.0
    assert summary.arrays[0].mean_value == 2.5


def build_tar_bytes(entries: dict[str, np.ndarray | bytes]) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for filename, payload in entries.items():
            if isinstance(payload, np.ndarray):
                payload_buffer = BytesIO()
                np.save(payload_buffer, payload)
                data = payload_buffer.getvalue()
            else:
                data = payload

            info = tarfile.TarInfo(filename)
            info.size = len(data)
            archive.addfile(info, BytesIO(data))

    return buffer.getvalue()
