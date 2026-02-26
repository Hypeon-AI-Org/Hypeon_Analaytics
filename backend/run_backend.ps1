# Run backend with live logs (unbuffered, INFO level so request logs show without DEBUG noise).
# Usage: .\run_backend.ps1   or   pwsh -File run_backend.ps1
$env:PYTHONUNBUFFERED = "1"
if (-not $env:LOG_LEVEL) { $env:LOG_LEVEL = "INFO" }
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
