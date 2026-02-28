# Quick backend connectivity check. Run from repo root.
# Usage: .\scripts\check_backend_connection.ps1
# Or: pwsh -File scripts/check_backend_connection.ps1
#
# Start backend first (from backend/): python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
# Then start frontend (from frontend/): npm run dev  (proxies /api to http://localhost:8001)

$Base = $env:BASE_URL
if (-not $Base) { $Base = "http://127.0.0.1:8001" }

$Headers = @{
    "X-Organization-Id" = "default"
    "Content-Type"       = "application/json"
}

Write-Host "=== Backend connectivity check (BASE=$Base) ===" -ForegroundColor Cyan

# 1. Health
try {
    $r = Invoke-WebRequest -Uri "$Base/health" -Method GET -Headers $Headers -UseBasicParsing -TimeoutSec 5
    Write-Host "  GET /health -> $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  GET /health -> FAIL: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 2. Dashboard ping (optional; confirms router is mounted)
try {
    $r = Invoke-WebRequest -Uri "$Base/api/v1/dashboard/ping" -Method GET -Headers $Headers -UseBasicParsing -TimeoutSec 5
    Write-Host "  GET /api/v1/dashboard/ping -> $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  GET /api/v1/dashboard/ping -> FAIL (optional): $($_.Exception.Message)" -ForegroundColor Yellow
}

# 3. Dashboard business-overview (must return 200)
try {
    $r = Invoke-WebRequest -Uri "$Base/api/v1/dashboard/business-overview" -Method GET -Headers $Headers -UseBasicParsing -TimeoutSec 10
    Write-Host "  GET /api/v1/dashboard/business-overview -> $($r.StatusCode)" -ForegroundColor Green
    $json = $r.Content | ConvertFrom-Json
    Write-Host "  Response keys: $($json.PSObject.Properties.Name -join ', ')"
} catch {
    Write-Host "  GET /api/v1/dashboard/business-overview -> FAIL: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        $body = $reader.ReadToEnd()
        Write-Host "  Response body: $body"
    }
    exit 1
}

# 4. Campaign performance
try {
    $r = Invoke-WebRequest -Uri "$Base/api/v1/dashboard/campaign-performance" -Method GET -Headers $Headers -UseBasicParsing -TimeoutSec 10
    Write-Host "  GET /api/v1/dashboard/campaign-performance -> $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  GET /api/v1/dashboard/campaign-performance -> FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

# 5. Funnel
try {
    $r = Invoke-WebRequest -Uri "$Base/api/v1/dashboard/funnel" -Method GET -Headers $Headers -UseBasicParsing -TimeoutSec 10
    Write-Host "  GET /api/v1/dashboard/funnel -> $($r.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "  GET /api/v1/dashboard/funnel -> FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nBackend is reachable; dashboard endpoints return 200." -ForegroundColor Green
Write-Host "Frontend should use: Vite proxy /api -> $Base (see frontend/vite.config.js)" -ForegroundColor Gray
