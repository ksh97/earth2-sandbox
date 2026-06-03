# earth2-sandbox

NVIDIA Earth-2 / FourCastNet 기반 AI 기상예보 애플리케이션을 만들기 위한 실험용 저장소입니다.

이 프로젝트의 첫 목표는 App Store와 Google Play에 동시에 출시할 수 있는 모바일 앱을 만들기 전에, 모바일 앱이 호출할 안정적인 백엔드 API를 먼저 정의하는 것입니다. FourCastNet NIM은 큰 기상 격자 데이터를 다루므로, 휴대폰에서 모델을 직접 실행하기보다 백엔드에서 추론과 후처리를 맡고 모바일 앱은 요약된 예보, 지도 타일, 차트 데이터를 받는 구조가 현실적입니다.

## 현재 상태

- FastAPI 기반 모듈러 모놀리스 백엔드
- Clean Architecture / port-adapter 방향의 `domain`, `application`, `infrastructure` 분리
- mock/FourCastNet 전환을 위한 forecast provider 구조
- provider status, queued forecast job, polling, retry/cancel/cleanup API
- OpenAPI snapshot 기반 API contract
- Expo 기반 iOS/Android 모바일 앱 prototype
- 백엔드 hardening과 프론트엔드/UI 개발을 병행하기 위한 문서와 테스트

## 프로젝트 구조

```text
earth2-sandbox/
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ .github/
│  ├─ pull_request_template.md
│  └─ workflows/
│     └─ ci.yml
├─ configs/
│  └─ config.example.yaml
├─ contracts/
│  ├─ README.md
│  └─ openapi/
│     └─ earth2-api.v1.yaml
├─ apps/
│  └─ mobile/
│     ├─ App.tsx
│     ├─ package.json
│     ├─ package-lock.json
│     └─ src/
│        ├─ api/
│        ├─ components/
│        ├─ hooks/
│        ├─ screens/
│        └─ utils/
├─ docs/
│  ├─ ARCHITECTURE.md
│  └─ ROADMAP.md
├─ tools/
│  ├─ dev_doctor.py
│  ├─ replay_fourcastnet_sample.py
│  └─ smoke_hosted_fourcastnet.py
├─ src/
│  └─ earth2_sandbox/
│     ├─ api/
│     │  └─ http/v1/routers/
│     ├─ application/
│     │  ├─ commands/
│     │  ├─ ports/
│     │  ├─ queries/
│     │  └─ services/
│     ├─ bootstrap/
│     │  ├─ app_factory.py
│     │  ├─ container.py
│     │  └─ settings.py
│     ├─ domain/
│     │  └─ jobs/
│     ├─ infrastructure/
│     │  ├─ nvidia/
│     │  ├─ providers/
│     │  ├─ queue/
│     │  ├─ runtime/
│     │  └─ storage/
│     ├─ app.py
│     ├─ config.py
│     ├─ main.py
│     ├─ clients/
│     ├─ providers/
│     ├─ postprocessing/
│     ├─ schemas/
│     ├─ services/
│     ├─ storage/
│     ├─ workers.py
│     └─ __init__.py
├─ tests/
│  ├─ contract/
│  ├─ fixtures/
│  └─ test_*.py
├─ notebooks/
│  └─ README.md
└─ data/
   └─ README.md
```

## 빠른 시작

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
python -m uvicorn earth2_sandbox.main:app --reload
```

서버가 켜지면 다음 주소를 확인합니다.

- 개발 진단: `.\.venv\Scripts\python.exe tools\dev_doctor.py`
- API 상태: http://127.0.0.1:8000/health
- API 인덱스: http://127.0.0.1:8000/
- 예보 provider 상태: http://127.0.0.1:8000/api/v1/forecast/provider/status
- 점 예보: http://127.0.0.1:8000/api/v1/forecast/point?latitude=37.5665&longitude=126.9780
- queued 예보 job 생성: `POST http://127.0.0.1:8000/api/v1/forecast/jobs`
- 예전 prototype 호환 예보: http://127.0.0.1:8000/api/v1/forecast/sample?latitude=37.5665&longitude=126.9780
- Swagger 문서: http://127.0.0.1:8000/docs

Hosted NVIDIA API 실험을 할 때는 `.env`에서 다음 값을 설정한 뒤 서버를 재시작합니다.

```powershell
EARTH2_FORECAST_PROVIDER=fourcastnet
EARTH2_FOURCASTNET_ENDPOINT_MODE=hosted
EARTH2_NVIDIA_API_KEY=your_nvidia_api_key
EARTH2_FOURCASTNET_CACHE_ENABLED=true
EARTH2_FOURCASTNET_CACHE_DIR=./data/cache/fourcastnet
EARTH2_FORECAST_JOB_STORE_BACKEND=file
EARTH2_FORECAST_JOB_STORE_DIR=./data/jobs
EARTH2_FORECAST_JOB_RETENTION_HOURS=168
```

첫 hosted inference adapter는 다음 엔드포인트로 호출할 수 있습니다.

- Hosted FourCastNet inference: http://127.0.0.1:8000/api/v1/forecast/fourcastnet/hosted/infer

응답에는 raw model output 자체가 아니라 byte length, sha256 digest, content type, tar/NumPy metadata, post-processing report가 포함됩니다. 실제 모바일 예보로 쓰려면 디코딩된 lead time/batch 배열 metadata를 바탕으로 특정 좌표 값을 샘플링하고 기존 `ForecastSummary` 계약으로 변환하는 단계가 추가로 필요합니다.

`EARTH2_FORECAST_PROVIDER=fourcastnet`와 hosted API key가 설정되어 있으면 기존 sample forecast 엔드포인트도 hosted FourCastNet tar 결과를 호출한 뒤 특정 위도/경도에 가장 가까운 격자점을 샘플링하여 `ForecastSummary` 형태로 반환합니다.

- Point forecast: http://127.0.0.1:8000/api/v1/forecast/point?latitude=37.5665&longitude=126.9780
- Queued forecast job: http://127.0.0.1:8000/api/v1/forecast/jobs
- Recent forecast jobs: http://127.0.0.1:8000/api/v1/forecast/jobs?limit=20

`POST /api/v1/forecast/jobs`는 장시간 hosted 호출을 대비한 첫 job 계약입니다. 응답은 즉시 `queued` 상태와 job id를 반환하고, 백그라운드 worker가 forecast provider를 호출한 뒤 `GET /api/v1/forecast/jobs/{job_id}`에서 `running`, `succeeded`, `failed`, `cancelled` 상태와 forecast/diagnostics/event history를 확인할 수 있게 합니다. `GET /api/v1/forecast/jobs/{job_id}/poll`은 모바일이 자주 호출할 수 있는 가벼운 polling 응답만 반환하고, `POST /api/v1/forecast/jobs/{job_id}/cancel`은 아직 끝나지 않은 job을 취소 상태로 전환합니다. 완료된 job은 `POST /api/v1/forecast/jobs/{job_id}/retry`로 같은 좌표의 새 attempt job을 만들 수 있습니다. `GET /api/v1/forecast/jobs?limit=20&status=succeeded`로 최근 job 목록도 조회할 수 있고, `POST /api/v1/forecast/jobs/cleanup`은 보존 기간이 지난 terminal job 파일을 정리합니다. 기본 구현은 프로세스 내 in-memory queue입니다. 실제 hosted 호출을 관찰할 때는 `EARTH2_FORECAST_JOB_STORE_BACKEND=file`로 바꾸면 `EARTH2_FORECAST_JOB_STORE_DIR` 아래에 job 상태와 diagnostics가 JSON 파일로 남습니다. 서버 시작 시 남아 있는 `queued` job은 worker로 다시 들어가고, `running` job은 `queued`로 복구 후 재시도됩니다. `EARTH2_FORECAST_JOB_STALE_TIMEOUT_SECONDS`보다 오래 멈춘 active job은 `failed`로 전환되어 무한 polling을 피합니다. API 응답에는 로컬 파일 경로를 노출하지 않고 cache artifact id만 표시합니다. 계약이 안정되면 Redis/Celery 또는 별도 worker 서비스로 교체할 수 있는 경계로 분리되어 있습니다.

## 프론트엔드/UI 개발 계약

프론트엔드 개발은 이제 mock provider와 queued forecast job 계약을 기준으로 진행할 수 있습니다. 모바일 앱은 `POST /api/v1/forecast/jobs`로 예보 job을 만들고, `GET /api/v1/forecast/jobs/{job_id}/poll`로 `queued`, `running`, `succeeded`, `failed`, `cancelled` 흐름을 가볍게 표시한 뒤, terminal 상태에서 `GET /api/v1/forecast/jobs/{job_id}`로 forecast payload, diagnostics, event history를 가져옵니다.

우선순위는 지도나 애니메이션보다 상태 경험입니다. 위치 입력과 preset 도시 선택, provider status badge, job progress panel, polling 상태, skeleton loading, 실패 원인 카드, retry affordance, 최근 job history, timeline chart, confidence/signal 표시를 먼저 다듬습니다. 백엔드는 freeze가 아니라 CI, queue 회귀 방지, OpenAPI snapshot, durable queue/store 설계, observability, auth/rate limit을 hardening backlog로 관리합니다.

실제 NVIDIA API key는 `.env`에만 저장하고 GitHub에는 올리지 않습니다. 샘플 tar 응답 파일을 받은 경우에도 `data/` 아래 로컬 파일로만 보관하고 커밋하지 않습니다.

Hosted API smoke test는 다음 명령으로 실행할 수 있습니다. 이 스크립트는 key를 출력하지 않고, tar가 직접 내려오면 `data/samples/`에 저장합니다.

```powershell
.\.venv\Scripts\python.exe tools\smoke_hosted_fourcastnet.py
```

Hosted API가 tar 본문을 즉시 반환하지 않으면 backend client는 NVCF request id로 status endpoint를 polling하고, `302 Location` 또는 JSON `responseReference`가 제공될 때 큰 결과물을 다운로드합니다. 다운로드된 tar는 `EARTH2_FOURCASTNET_CACHE_DIR` 아래에 요청 payload digest 기준으로 저장되어 같은 요청을 로컬에서 재현할 수 있습니다.

실제 호출이 `504`와 `nvcf-status=errored`로 실패할 때는 앱 데이터 경로가 tar decoding까지 도달하지 못한 상태입니다. 이 경우 queued job은 `failed`로 끝나며 `diagnostics`에 가능한 범위의 `nvcf_request_id`, `nvcf_status`, `response_source`, `byte_length`, `poll_attempts`, `message`를 남깁니다. `provider/status`의 `ready=true`는 API key와 hosted endpoint 설정이 있다는 뜻이고, 실제 FourCastNet output 품질이나 tar 다운로드 성공을 보장하지 않습니다. 먼저 smoke test 결과가 tar, `responseReference`, `Large asset written`, `504/errored` 중 어느 경로인지 분류한 뒤 fixture/golden test를 확장합니다.

저장된 tar 또는 `data/samples/`의 샘플 tar를 다시 디코딩해보려면 다음 명령을 사용합니다.

```powershell
.\.venv\Scripts\python.exe tools\replay_fourcastnet_sample.py
.\.venv\Scripts\python.exe tools\replay_fourcastnet_sample.py data\samples\example.tar
```

현재 hosted API가 tar 본문, `302 Location`, 또는 JSON `responseReference` 없이 `{"message": "Large asset written"}` JSON marker만 반환할 수 있습니다. 이 경우 API key와 요청 자체는 동작하지만, point forecast 샘플링을 완료하려면 다운로드 가능한 tar 참조가 필요합니다.

## 모바일 앱 시작

```powershell
cd apps/mobile
npm install
Copy-Item .env.example .env
npm run start
```

Android Emulator에서 로컬 백엔드에 접속할 때는 `http://10.0.2.2:8000`을 사용합니다. iOS Simulator에서는 보통 `http://127.0.0.1:8000`을 사용할 수 있습니다.

## 개발 원칙

- 진짜 API 키는 GitHub에 올리지 않습니다.
- 대용량 기상 데이터, 모델 체크포인트, 산출물은 GitHub에 올리지 않습니다.
- 처음에는 mock API로 모바일 화면과 API 계약을 검증합니다.
- FourCastNet NIM 연동은 백엔드에서 숨기고, 앱은 단순한 JSON API만 호출하게 만듭니다.
- `.env`에서 `EARTH2_FORECAST_PROVIDER=mock` 또는 `fourcastnet`으로 backend provider를 전환합니다.
- 첫 실제 추론 실험은 hosted NVIDIA API 경로로 진행하고, self-hosted NIM은 GPU/Docker/ERA5 입력 준비 후 붙입니다.

## 참고 문서

- NVIDIA FourCastNet NIM 문서: https://docs.nvidia.com/nim/earth-2/fourcastnet/latest/
- NVIDIA Earth-2 Weather Analytics Blueprint: https://github.com/NVIDIA-Omniverse-blueprints/earth2-weather-analytics
