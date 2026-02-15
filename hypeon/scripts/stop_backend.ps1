# Stop all processes listening on port 8000 (keeps 5173 frontend and 5433 Postgres)
$ErrorActionPreference = "SilentlyContinue"
$conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$pids = $conns.OwningProcess | Sort-Object -Unique
foreach ($p in $pids) {
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped PID $p (was on port 8000)"
}
if ($pids.Count -eq 0) { Write-Host "No process was using port 8000." }
else { Write-Host "Port 8000 is now free. Run .\scripts\run_backend.ps1 to start one backend." }
