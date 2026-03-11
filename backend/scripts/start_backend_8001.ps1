# Free port 8001 and start backend with .env loaded
$ErrorActionPreference = "SilentlyContinue"
Get-NetTCPConnection -LocalPort 8001 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
Start-Sleep -Seconds 3
$root = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Get-Content "$root\.env" | ForEach-Object {
  if ($_ -match '^\s*([^#=]+)=(.*)$') {
    $n = $matches[1].Trim()
    $v = $matches[2].Trim() -replace '^["'']|["'']$'
    [Environment]::SetEnvironmentVariable($n, $v, 'Process')
  }
}
Set-Location (Join-Path $root "backend")
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
