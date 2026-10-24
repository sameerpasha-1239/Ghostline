# Rubric-Local Clean Windows Uninstaller Script
# Safely terminates processes, removes shortcuts, cleans registry, and manages user data

Write-Host "==========================================================" -ForegroundColor Red
Write-Host "  Rubric-Local Application Uninstaller" -ForegroundColor Red
Write-Host "==========================================================" -ForegroundColor Red

# 1. Terminate running instances
Write-Host "`n[*] Terminating any running Rubric-Local processes..." -ForegroundColor Yellow
$proc = Get-Process -Name "Rubric-Local" -ErrorAction SilentlyContinue
if ($proc) {
    $proc | Stop-Process -Force
    Start-Sleep -Seconds 1
    Write-Host "  [+] Active Rubric-Local process terminated." -ForegroundColor Green
} else {
    Write-Host "  [+] No active process found." -ForegroundColor Gray
}

# 2. Remove Shortcuts
Write-Host "[*] Removing shortcuts..." -ForegroundColor Yellow
$startMenuLnk = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Rubric-Local.lnk"
if (Test-Path $startMenuLnk) {
    Remove-Item -Path $startMenuLnk -Force
    Write-Host "  [+] Removed Start Menu shortcut." -ForegroundColor Green
}

$desktopLnk = Join-Path ([System.Environment]::GetFolderPath("Desktop")) "Rubric-Local.lnk"
if (Test-Path $desktopLnk) {
    Remove-Item -Path $desktopLnk -Force
    Write-Host "  [+] Removed Desktop shortcut." -ForegroundColor Green
}

# 3. Clean Windows Registry Entry
Write-Host "[*] Cleaning Windows Settings registration..." -ForegroundColor Yellow
$regKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\RubricLocal"
if (Test-Path $regKey) {
    Remove-Item -Path $regKey -Recurse -Force
    Write-Host "  [+] Unregistered from Windows Add/Remove Programs." -ForegroundColor Green
}

# 4. Handle User Configuration and History Data (%APPDATA%\RubricLocal)
$appDataDir = Join-Path $env:APPDATA "RubricLocal"
if (Test-Path $appDataDir) {
    $keep = Read-Host "`nDo you want to KEEP your saved questions and settings in $appDataDir? (Y/n)"
    if ($keep -match "^[nN]") {
        Remove-Item -Path $appDataDir -Recurse -Force
        Write-Host "  [+] Removed user settings and history data." -ForegroundColor Green
    } else {
        Write-Host "  [+] User configuration preserved for future re-installation." -ForegroundColor Cyan
    }
}

# 5. Remove Program Files from %LOCALAPPDATA%\Programs\Rubric-Local
$installDir = Join-Path $env:LOCALAPPDATA "Programs\Rubric-Local"
if (Test-Path $installDir) {
    Write-Host "`n[*] Removing program files from $installDir..." -ForegroundColor Yellow
    # Self-deleting batch job for the uninstall directory
    $tempBat = Join-Path $env:TEMP "rubric_local_cleanup.bat"
    $batContent = @"
@echo off
timeout /t 2 /nobreak >nul
rmdir /s /q "$installDir"
del "%~f0"
"@
    Set-Content -Path $tempBat -Value $batContent
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$tempBat`"" -WindowStyle Hidden
    Write-Host "  [+] Program removal initiated." -ForegroundColor Green
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  UNINSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "  Rubric-Local has been cleanly removed from your system." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
