# One-command local run: UV backend + Vite frontend
# Usage (from repo root):
#   .\dev.ps1
#
# Optional: .\dev.ps1 -SkipSync   (skip uv sync / npm install)

param(
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Assert-CommandExists([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

Assert-CommandExists uv
Assert-CommandExists npm
Assert-CommandExists node

Write-Host "[dev] UV $(uv --version)" -ForegroundColor Cyan
Write-Host "[dev] Node $(node --version) / npm $(npm --version)" -ForegroundColor Cyan

if (-not $SkipSync) {
    Write-Host "[dev] syncing Python deps with uv ..." -ForegroundColor Cyan
    uv sync --project (Join-Path $Root "backend") --directory (Join-Path $Root "backend")

    $nodeModules = Join-Path $Root "frontend\node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Host "[dev] installing frontend npm deps ..." -ForegroundColor Cyan
        npm install --prefix (Join-Path $Root "frontend")
    }
}

# Free ports if stale processes linger (common on Windows with --reload zombies)
foreach ($port in 8000, 5173) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        try {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-Host "[dev] freed port $port (pid $($c.OwningProcess))" -ForegroundColor Yellow
        } catch {}
    }
}

Write-Host "[dev] starting app ..." -ForegroundColor Green
uv run --project (Join-Path $Root "backend") --directory (Join-Path $Root "backend") `
    python (Join-Path $Root "scripts\run_app.py")
