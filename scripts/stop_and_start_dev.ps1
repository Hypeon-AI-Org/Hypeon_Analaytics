# Stop processes on backend (8001), then start backend and frontend.
# Run from repo root: .\scripts\stop_and_start_dev.ps1
# If port 8001 stays in use, close any other terminal/IDE running the backend, or run PowerShell as Administrator.

$ErrorActionPreference = "SilentlyContinue"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path (Join-Path $repoRoot "backend"))) { $repoRoot = (Get-Location).Path }

Write-Host "Stopping processes on port 8001..."
$pids8001 = (Get-NetTCPConnection -LocalPort 8001 -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
foreach ($p in $pids8001) {
    if ($p -gt 0 -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $p -Force; Write-Host "  Stopped PID $p"
    }
}
# Fallback: parse netstat for LISTENING on 8001
$lines = netstat -ano | Select-String ":8001.*LISTENING"
foreach ($line in $lines) {
    $parts = ($line -split '\s+'); $procId = $parts[-1]
    if ($procId -match '^\d+$' -and (Get-Process -Id ([int]$procId) -ErrorAction SilentlyContinue)) {
        Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue; Write-Host "  Stopped PID $procId"
    }
}
Start-Sleep -Seconds 2

Write-Host "Starting backend on http://127.0.0.1:8001 ..."
$env:PYTHONPATH = Join-Path $repoRoot "backend"
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001" -WorkingDirectory $repoRoot -NoNewWindow:$false -PassThru | Out-Null
Start-Sleep -Seconds 2

Write-Host "Starting frontend (Vite)..."
Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory (Join-Path $repoRoot "frontend") -NoNewWindow:$false -PassThru | Out-Null

Write-Host "Done. Backend: http://127.0.0.1:8001  |  Frontend: check terminal for URL (e.g. http://localhost:5173)"
