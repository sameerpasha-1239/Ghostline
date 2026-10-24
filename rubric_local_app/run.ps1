param(
    [switch]$Dev
)

# PowerShell launcher for Rubric-Local
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if ($Dev) {
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  Rubric-Local Developer Console (Interactive)" -ForegroundColor Cyan
    Write-Host "  Trigger Hotkey: Alt + /   |   Real-time Logging Active" -ForegroundColor Yellow
    Write-Host "========================================================" -ForegroundColor Cyan
    python rubric_local\app.py
} else {
    Write-Host "[*] Launching Rubric-Local in background (Console Hidden)..." -ForegroundColor Cyan
    Start-Process -FilePath "pythonw.exe" -ArgumentList "rubric_local\app.py" -WindowStyle Hidden
}
