# Start FastAPI backend on http://127.0.0.1:8000 (UV)
$ErrorActionPreference = "Stop"
$Backend = Join-Path $PSScriptRoot "..\backend"
Set-Location $Backend
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv not found. Install from https://docs.astral.sh/uv/ or use: pip install uvicorn && uvicorn ..."
}
uv sync --project $Backend --directory $Backend
uv run --project $Backend --directory $Backend uvicorn app.main:app --host 127.0.0.1 --port 8000
