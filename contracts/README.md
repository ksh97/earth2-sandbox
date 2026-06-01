# API Contracts

This directory contains committed contracts shared by the backend and clients.

- `openapi/earth2-api.v1.yaml` is the v1 FastAPI OpenAPI snapshot.
- `tests/contract/test_openapi_snapshot.py` fails when the running app's OpenAPI output
  differs from the committed snapshot.

Regenerate the snapshot after an intentional API contract change:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; import yaml; from earth2_sandbox.app import create_app; from earth2_sandbox.config import Settings; app = create_app(settings=Settings(forecast_provider='mock', fourcastnet_endpoint_mode='self_hosted', nvidia_api_key=None)); Path('contracts/openapi/earth2-api.v1.yaml').write_text(yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True), encoding='utf-8')"
```

