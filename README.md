# earth2-sandbox

NVIDIA Earth-2 / FourCastNet 기반 AI 기상예보 애플리케이션을 만들기 위한 실험용 저장소입니다.

이 프로젝트의 첫 목표는 App Store와 Google Play에 동시에 출시할 수 있는 모바일 앱을 만들기 전에, 모바일 앱이 호출할 안정적인 백엔드 API를 먼저 정의하는 것입니다. FourCastNet NIM은 큰 기상 격자 데이터를 다루므로, 휴대폰에서 모델을 직접 실행하기보다 백엔드에서 추론과 후처리를 맡고 모바일 앱은 요약된 예보, 지도 타일, 차트 데이터를 받는 구조가 현실적입니다.

## 현재 상태

- Python 백엔드 skeleton
- 설정 파일과 환경변수 예시
- mock/FourCastNet 전환을 위한 forecast provider 구조
- 모바일 앱 개발 전에 사용할 mock forecast API와 provider status API
- Expo 기반 iOS/Android 모바일 앱 prototype
- 초보자용 로드맵과 아키텍처 문서

## 프로젝트 구조

```text
earth2-sandbox/
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ configs/
│  └─ config.example.yaml
├─ apps/
│  └─ mobile/
│     ├─ App.tsx
│     ├─ package.json
│     └─ src/
├─ docs/
│  ├─ ARCHITECTURE.md
│  └─ ROADMAP.md
├─ src/
│  └─ earth2_sandbox/
│     ├─ app.py
│     ├─ config.py
│     ├─ main.py
│     ├─ clients/
│     │  └─ nim.py
│     ├─ providers/
│     │  ├─ base.py
│     │  ├─ factory.py
│     │  ├─ fourcastnet.py
│     │  └─ mock.py
│     ├─ schemas/
│     │  └─ forecast.py
│     └─ services/
│        └─ forecast.py
├─ tests/
│  ├─ test_api_contract.py
│  ├─ test_fourcastnet_provider.py
│  └─ test_mock_forecast.py
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

- API 상태: http://127.0.0.1:8000/health
- 예보 provider 상태: http://127.0.0.1:8000/api/v1/forecast/provider/status
- 예시 예보: http://127.0.0.1:8000/api/v1/forecast/sample?latitude=37.5665&longitude=126.9780
- Swagger 문서: http://127.0.0.1:8000/docs

Hosted NVIDIA API 실험을 할 때는 `.env`에서 다음 값을 설정한 뒤 서버를 재시작합니다.

```powershell
EARTH2_FORECAST_PROVIDER=fourcastnet
EARTH2_FOURCASTNET_ENDPOINT_MODE=hosted
EARTH2_NVIDIA_API_KEY=your_nvidia_api_key
```

첫 hosted inference adapter는 다음 엔드포인트로 호출할 수 있습니다.

- Hosted FourCastNet inference: http://127.0.0.1:8000/api/v1/forecast/fourcastnet/hosted/infer

응답에는 raw model output 자체가 아니라 byte length, sha256 digest, content type, post-processing report가 포함됩니다. 실제 모바일 예보로 쓰려면 tar/NumPy 결과를 백엔드에서 디코딩하고 기존 `ForecastSummary` 계약으로 변환하는 단계가 추가로 필요합니다.

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
