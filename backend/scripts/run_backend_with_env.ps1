# Run backend with .env vars (including API_KEY) so uvicorn worker has them.
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $val = $matches[2].Trim() -replace '^["'']|["'']$'
            [Environment]::SetEnvironmentVariable($name, $val, "Process")
        }
    }
}
Set-Location (Join-Path $root "backend")
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
