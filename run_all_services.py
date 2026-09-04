"""Launch all five backend services from a single entrypoint.

This script starts each FastAPI app in its own process using the service's
local virtual environment when available, otherwise it falls back to the
current Python interpreter.
"""

from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
SERVICES = [
    ("task1-route-service", 8001),
    ("task2-resource-service", 8002),
    ("task3-network-service", 8003),
    ("task4-decision-service", 8004),
    ("task5-optimization-service", 8005),
]


def resolve_python(service_dir: Path) -> str:
    """Return the best Python executable for a service."""
    venv_python = service_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def start_service(service_name: str, port: int) -> subprocess.Popen[str]:
    """Start one FastAPI service in its own process."""
    service_dir = ROOT_DIR / service_name
    python_exe = resolve_python(service_dir)
    return subprocess.Popen(
        [
            python_exe,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--port",
            str(port),
            "--host",
            "0.0.0.0",
        ],
        cwd=service_dir,
    )


def main() -> int:
    """Start all services and keep the launcher alive until interrupted."""
    processes: list[subprocess.Popen[str]] = []

    try:
        for service_name, port in SERVICES:
            print(f"Starting {service_name} on port {port}...")
            processes.append(start_service(service_name, port))

        print("\nAll services are running. Press Ctrl+C to stop them.")

        for process in processes:
            process.wait()
        return 0
    except KeyboardInterrupt:
        print("\nStopping services...")
        return 130
    finally:
        for process in processes:
            if process.poll() is None:
                if sys.platform == "win32":
                    process.terminate()
                else:
                    process.send_signal(signal.SIGTERM)


if __name__ == "__main__":
    raise SystemExit(main())
