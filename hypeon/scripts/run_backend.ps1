# Run API backend with Docker Postgres (port 5433). Use this if the app still connects to 5432.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$env:DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5433/hypeon"
$env:PYTHONPATH = "."

# Load .env from workspace root for GEMINI_* etc.
$envFile = (Resolve-Path "..\.env" -ErrorAction SilentlyContinue)
if ($envFile) { Get-Content $envFile | ForEach-Object { if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$' -and $_ -notmatch '^\s*#') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process') } } }

Write-Host "Starting API (DATABASE_URL=$env:DATABASE_URL)"
python -m uvicorn apps.api.src.app:app --reload --host 0.0.0.0 --port 8000
