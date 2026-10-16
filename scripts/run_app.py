"""Start backend (FastAPI) + frontend (Vite) with one process group.

Usage (from repo root):
  uv run --project backend --directory backend python ..\\scripts\\run_app.py

Or simply:
  .\\dev.ps1
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

BACKEND_HOST = os.environ.get("CLAIMS_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = os.environ.get("CLAIMS_BACKEND_PORT", "8000")
FRONTEND_HOST = os.environ.get("CLAIMS_FRONTEND_HOST", "127.0.0.1")
FRONTEND_PORT = os.environ.get("CLAIMS_FRONTEND_PORT", "5173")


def _resolve_cmd(args: list[str]) -> list[str]:
    """Resolve npm/node shims on Windows (npm.cmd etc.)."""
    if not args:
        return args
    resolved = shutil.which(args[0])
    if resolved:
        return [resolved, *args[1:]]
    if sys.platform == "win32":
        for suffix in (".cmd", ".bat", ".exe"):
            resolved = shutil.which(args[0] + suffix)
            if resolved:
                return [resolved, *args[1:]]
    return args


def _popen(args: list[str], cwd: Path, name: str) -> subprocess.Popen:
    args = _resolve_cmd(args)
    creationflags = 0
    if sys.platform == "win32":
        # New process group so Ctrl+C / terminate can clean children
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    print(f"[dev] starting {name}: {' '.join(args)}  (cwd={cwd})")
    return subprocess.Popen(
        args,
        cwd=str(cwd),
        env=os.environ.copy(),
        creationflags=creationflags,
    )


def _terminate(proc: subprocess.Popen | None, name: str) -> None:
    if proc is None or proc.poll() is not None:
        return
    print(f"[dev] stopping {name} (pid={proc.pid})")
    try:
        if sys.platform == "win32":
            proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            try:
                proc.wait(timeout=3)
                return
            except subprocess.TimeoutExpired:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception as exc:  # noqa: BLE001
        print(f"[dev] warn: could not stop {name}: {exc}")
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    if not (BACKEND / "app" / "main.py").exists():
        print(f"[dev] backend not found at {BACKEND}", file=sys.stderr)
        return 1
    if not (FRONTEND / "package.json").exists():
        print(f"[dev] frontend not found at {FRONTEND}", file=sys.stderr)
        return 1
    if not (FRONTEND / "node_modules").exists():
        print("[dev] frontend/node_modules missing — run: npm install --prefix frontend")
        return 1

    # Prefer the interpreter that launched us (uv-managed).
    py = sys.executable
    backend = _popen(
        [
            py,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            BACKEND_HOST,
            "--port",
            BACKEND_PORT,
        ],
        cwd=BACKEND,
        name="backend",
    )
    frontend = _popen(
        [
            "npm",
            "run",
            "dev",
            "--",
            "--host",
            FRONTEND_HOST,
            "--port",
            FRONTEND_PORT,
        ],
        cwd=FRONTEND,
        name="frontend",
    )

    print()
    print(f"[dev] Backend   http://{BACKEND_HOST}:{BACKEND_PORT}")
    print(f"[dev] Frontend  http://{FRONTEND_HOST}:{FRONTEND_PORT}")
    print("[dev] Ctrl+C to stop both")
    print()

    code = 0
    try:
        while True:
            b = backend.poll()
            f = frontend.poll()
            if b is not None:
                print(f"[dev] backend exited with code {b}")
                code = b or 1
                break
            if f is not None:
                print(f"[dev] frontend exited with code {f}")
                code = f or 1
                break
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\n[dev] interrupted")
        code = 0
    finally:
        _terminate(frontend, "frontend")
        _terminate(backend, "backend")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
