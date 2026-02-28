# Fetch copilot answer for: "What is the views count of Item Id starting with FT05B coming from Google?"
# Requires backend running on port 8001. Run from repo root: .\scripts\fetch_ft05b_google_views_answer.ps1

$Base = $env:COPILOT_BASE_URL
if (-not $Base) { $Base = "http://127.0.0.1:8001" }

$body = @{ message = "What is the views count of Item Id starting with FT05B coming from Google?" } | ConvertTo-Json
$headers = @{
    "Content-Type"       = "application/json"
    "X-Organization-Id"  = "default"
}

Write-Host "Asking copilot: 'What is the views count of Item Id starting with FT05B coming from Google?'" -ForegroundColor Cyan
Write-Host "Backend: $Base" -ForegroundColor Gray
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri "$Base/api/v1/copilot/chat" -Method POST -Body $body -Headers $headers -TimeoutSec 120
    Write-Host "Answer:" -ForegroundColor Green
    Write-Host $response.answer
    if ($response.data -and $response.data.Count -gt 0) {
        Write-Host ""
        Write-Host "Data ($($response.data.Count) row(s)):" -ForegroundColor Green
        $response.data | Format-Table -AutoSize
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        Write-Host $reader.ReadToEnd()
    }
    exit 1
}
