# Start Vite frontend on http://127.0.0.1:5173
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\frontend")
npm run dev
