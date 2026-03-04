# Build frontend image with VITE_* from .env (Firebase + API base).
# Usage: from repo root: .\scripts\build_frontend.ps1 [-BackendUrl "https://..."]
# Optional: -BackendUrl overrides VITE_API_BASE (e.g. your Cloud Run backend URL).
# Prereqs: docker; .env in repo root with VITE_FIREBASE_* and optionally VITE_API_BASE.

param(
    [string]$BackendUrl = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$envFile = Join-Path $RepoRoot ".env"
$vars = @{}

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match "^([^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            if ($key -match "^VITE_") { $vars[$key] = $val }
        }
    }
}

if ($BackendUrl) {
    $vars["VITE_API_BASE"] = $BackendUrl.Trim()
} elseif (-not $vars["VITE_API_BASE"]) {
    Write-Host "Set VITE_API_BASE in .env or pass -BackendUrl 'https://your-backend.run.app'" -ForegroundColor Yellow
}

$Registry = "europe-north2-docker.pkg.dev/hypeon-ai-prod/hypeon-analytics"
$args = @(
    "build",
    "-f", "frontend/Dockerfile",
    "-t", "${Registry}/frontend:latest",
    "frontend"
)

foreach ($k in $vars.Keys) {
    $v = $vars[$k]
    if ([string]::IsNullOrEmpty($v)) { continue }
    $args += "--build-arg", "${k}=$v"
}

Write-Host "Building frontend with VITE_* from .env..." -ForegroundColor Cyan
& docker @args
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }

Write-Host "Frontend image: ${Registry}/frontend:latest" -ForegroundColor Green
Write-Host "Push and deploy: docker push ${Registry}/frontend:latest" -ForegroundColor Gray
