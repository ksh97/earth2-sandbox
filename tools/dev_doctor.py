"""Local development diagnostics for the Earth-2 sandbox.

The script intentionally avoids printing secrets. It reports whether expected
paths, local ports, and backend/frontend health checks look usable.
"""

from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MOBILE_ROOT = REPO_ROOT / "apps" / "mobile"
BACKEND_BASE_URL = "http://127.0.0.1:8000"
WEB_BASE_URL = "http://localhost:8081"


class Doctor:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, label: str, detail: str) -> None:
        print(f"[OK]   {label}: {detail}")

    def warn(self, label: str, detail: str) -> None:
        self.warnings += 1
        print(f"[WARN] {label}: {detail}")

    def fail(self, label: str, detail: str) -> None:
        self.failures += 1
        print(f"[FAIL] {label}: {detail}")

    def finish(self) -> int:
        print()
        print(f"Doctor finished with {self.failures} failure(s), {self.warnings} warning(s).")
        return 1 if self.failures else 0


def main() -> int:
    doctor = Doctor()
    check_repo_path(doctor)
    check_expected_files(doctor)
    check_runtime_commands(doctor)
    check_env_files(doctor)
    check_ports_and_http(doctor)
    return doctor.finish()


def check_repo_path(doctor: Doctor) -> None:
    doctor.ok("repo root", str(REPO_ROOT))
    parts = {part.lower() for part in REPO_ROOT.parts}
    if "onedrive" in parts or any("onedrive" in part for part in parts):
        doctor.warn("repo path", "Repository is under OneDrive; C:\\dev\\earth2-sandbox is safer.")

    if platform.system() == "Windows":
        recommended = Path("C:/dev/earth2-sandbox")
        try:
            if REPO_ROOT.resolve() != recommended.resolve():
                doctor.warn("repo path", f"Recommended Windows path is {recommended}.")
        except OSError:
            doctor.warn("repo path", f"Recommended Windows path is {recommended}.")


def check_expected_files(doctor: Doctor) -> None:
    expected = [
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / ".env.example",
        REPO_ROOT / "src" / "earth2_sandbox" / "app.py",
        MOBILE_ROOT / "package.json",
        MOBILE_ROOT / ".env.example",
    ]
    for path in expected:
        if path.exists():
            doctor.ok("file", rel(path))
        else:
            doctor.fail("file", f"Missing {rel(path)}")


def check_runtime_commands(doctor: Doctor) -> None:
    commands = [
        ("python", [str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"), "--version"]),
        ("npm", [find_command("npm"), "--version"]),
        ("node", [find_command("node"), "--version"]),
    ]
    for label, command in commands:
        if not command[0]:
            doctor.fail(label, f"{label} was not found on PATH.")
            continue

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                cwd=REPO_ROOT,
                text=True,
                timeout=8,
            )
        except (OSError, subprocess.SubprocessError) as error:
            doctor.fail(label, str(error))
            continue

        output = (result.stdout or result.stderr).strip()
        if result.returncode == 0:
            doctor.ok(label, output)
        else:
            doctor.fail(label, output or f"Command exited {result.returncode}")


def find_command(command: str) -> str:
    return shutil.which(command) or ""


def check_env_files(doctor: Doctor) -> None:
    root_env = read_env(REPO_ROOT / ".env")
    mobile_env = read_env(MOBILE_ROOT / ".env")

    provider = root_env.get("EARTH2_FORECAST_PROVIDER")
    if provider:
        doctor.ok("backend env", f"EARTH2_FORECAST_PROVIDER={provider}")
    else:
        doctor.warn("backend env", ".env is missing or EARTH2_FORECAST_PROVIDER is not set.")

    api_key = root_env.get("EARTH2_NVIDIA_API_KEY")
    if api_key:
        doctor.ok("backend env", "EARTH2_NVIDIA_API_KEY is set without printing the value.")
    else:
        doctor.warn("backend env", "EARTH2_NVIDIA_API_KEY is empty; hosted mode will not run.")

    cache_dir = root_env.get("EARTH2_FOURCASTNET_CACHE_DIR", "./data/cache/fourcastnet")
    doctor.ok("backend env", f"EARTH2_FOURCASTNET_CACHE_DIR={cache_dir}")
    if Path(cache_dir).is_absolute():
        resolved_cache_dir = Path(cache_dir)
    else:
        resolved_cache_dir = REPO_ROOT / cache_dir
    if not _is_under(resolved_cache_dir, REPO_ROOT):
        doctor.warn("backend env", "FourCastNet cache dir is outside the repository workspace.")

    mobile_api = mobile_env.get("EXPO_PUBLIC_API_BASE_URL")
    if mobile_api:
        doctor.ok("mobile env", f"EXPO_PUBLIC_API_BASE_URL={mobile_api}")
    else:
        doctor.warn(
            "mobile env",
            "apps/mobile/.env is missing; platform fallback URLs will be used.",
        )


def check_ports_and_http(doctor: Doctor) -> None:
    check_port(doctor, "backend port", "127.0.0.1", 8000)
    check_port(doctor, "expo web port", "127.0.0.1", 8081)

    root = read_json(f"{BACKEND_BASE_URL}/")
    if root:
        doctor.ok("backend /", f"service={root.get('service')} status={root.get('status')}")
    else:
        doctor.warn("backend /", "Backend root did not return JSON.")

    health = read_json(f"{BACKEND_BASE_URL}/health")
    if health:
        doctor.ok(
            "backend health",
            f"provider={health.get('forecast_provider')} mock={health.get('mock_forecast')}",
        )
    else:
        doctor.warn("backend health", "Start uvicorn on 127.0.0.1:8000 to enable health checks.")

    status = read_json(f"{BACKEND_BASE_URL}/api/v1/forecast/provider/status")
    if status:
        status_summary = (
            f"provider={status.get('provider')} "
            f"ready={status.get('ready')} "
            f"mode={status.get('mode')}"
        )
        doctor.ok(
            "provider status",
            status_summary,
        )
    else:
        doctor.warn("provider status", "Provider status endpoint is not reachable.")

    if read_text(WEB_BASE_URL):
        doctor.ok("expo web", WEB_BASE_URL)
    else:
        doctor.warn("expo web", "Start Expo on port 8081 to preview the app in a browser.")


def check_port(doctor: Doctor, label: str, host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
    if result == 0:
        doctor.ok(label, f"{host}:{port} is listening")
    else:
        doctor.warn(label, f"{host}:{port} is not listening")


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_json(url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError):
        return None


def read_text(url: str) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.read(512).decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError):
        return None


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
