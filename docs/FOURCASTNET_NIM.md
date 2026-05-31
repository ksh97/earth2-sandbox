# FourCastNet NIM Integration

This backend can run in two modes:

- `EARTH2_ENABLE_MOCK_FORECAST=true`: return deterministic mock values for UI development.
- `EARTH2_ENABLE_MOCK_FORECAST=false`: call a FourCastNet NIM endpoint and summarize real model output.

The mobile app always calls the same backend endpoint:

```text
GET /api/v1/forecast/point?latitude=37.5665&longitude=126.9780
```

## What the Backend Does

When mock mode is disabled, the backend:

1. Checks `GET {EARTH2_NIM_BASE_URL}/v1/health/ready`.
2. Posts `EARTH2_FOURCASTNET_INPUT_ARRAY_PATH` to `{EARTH2_NIM_BASE_URL}/v1/infer`.
3. Saves the returned tar archive under `outputs/fourcastnet/`.
4. Opens the selected `{lead_hours}_000.npy` member.
5. Converts the requested latitude/longitude to the FourCastNet 0.25 degree grid.
6. Returns temperature, 10 m wind speed, mean sea level pressure, and total column water vapor.

## NIM Setup

Follow NVIDIA's FourCastNet NIM quickstart to pull and run the container. The current NVIDIA docs use:

```powershell
docker pull nvcr.io/nim/nvidia/fourcastnet:2.0.0
```

The container and model are large, so do this only on a machine with the required NVIDIA GPU setup and NGC access.

## Create the Input Array

The NIM expects an initial atmospheric state in NumPy `.npy` format. NVIDIA's quickstart uses Earth2Studio with ARCO ERA5:

```python
import numpy as np
from datetime import datetime
from earth2studio.data import ARCO
from earth2studio.models.px.fcn3 import VARIABLES

ds = ARCO()
da = ds(time=datetime(2023, 1, 1), variable=VARIABLES)
np.save("data/fcn_inputs.npy", da.to_numpy()[None].astype("float32"))
```

Keep this file in `data/`. The repository intentionally ignores `.npy`, `.tar`, and other generated weather artifacts.

## Backend Environment

Copy `.env.example` to `.env`, then set:

```text
EARTH2_ENABLE_MOCK_FORECAST=false
EARTH2_NIM_BASE_URL=http://localhost:8000
EARTH2_FOURCASTNET_INPUT_ARRAY_PATH=./data/fcn_inputs.npy
EARTH2_FOURCASTNET_INPUT_TIME=2023-01-01T00:00:00Z
EARTH2_FOURCASTNET_SIMULATION_LENGTH=1
EARTH2_FOURCASTNET_SUMMARY_LEAD_HOURS=6
```

Start the backend:

```powershell
python -m uvicorn earth2_sandbox.main:app --reload
```

Then test:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/forecast/point?latitude=37.5665&longitude=126.9780"
```

## Notes

- `simulation_length` is counted in 6-hour model steps.
- `summary_lead_hours=6` reads `006_000.npy`. If that member is not present, the backend uses the highest available lead time in the returned archive.
- `temperature` is converted from Kelvin to Celsius when needed.
- `mean_sea_level_pressure` is converted from Pa to hPa.
- The mobile app never receives the raw global forecast arrays.
