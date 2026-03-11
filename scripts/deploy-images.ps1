# Build, tag, and push backend + frontend to Artifact Registry
# Usage: from repo root: .\scripts\deploy-images.ps1
# Prereqs: gcloud CLI, docker; run: gcloud auth login && gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

$ErrorActionPreference = "Stop"
$Registry = "us-central1-docker.pkg.dev/hypeon-ai-prod/hypeon-analytics"
$RepoRoot = $PSScriptRoot + "\.."

Set-Location $RepoRoot

Write-Host "Building backend..." -ForegroundColor Cyan
docker build -t hypeon-backend -f backend/Dockerfile .
if ($LASTEXITCODE -ne 0) { throw "Backend build failed" }

Write-Host "Building frontend assets (npm run build)..." -ForegroundColor Cyan
Set-Location frontend
npm ci 2>$null; if ($LASTEXITCODE -ne 0) { npm install }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend npm run build failed" }
Set-Location $RepoRoot

Write-Host "Building frontend image..." -ForegroundColor Cyan
docker build -t hypeon-frontend -f frontend/Dockerfile ./frontend
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }

Write-Host "Tagging for Artifact Registry..." -ForegroundColor Cyan
docker tag hypeon-backend:latest "${Registry}/backend:latest"
docker tag hypeon-frontend:latest "${Registry}/frontend:latest"

Write-Host "Pushing to ${Registry}..." -ForegroundColor Cyan
docker push "${Registry}/backend:latest"
if ($LASTEXITCODE -ne 0) { throw "Backend push failed" }
docker push "${Registry}/frontend:latest"
if ($LASTEXITCODE -ne 0) { throw "Frontend push failed" }

Write-Host "Done. Images:" -ForegroundColor Green
Write-Host "  ${Registry}/backend:latest"
Write-Host "  ${Registry}/frontend:latest"
