# Rubric-Local Windows Application Installer
# Installs standalone Rubric-Local to %LOCALAPPDATA%\Programs\Rubric-Local
# Registers shortcuts and Windows Add/Remove Programs uninstaller

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Rubric-Local Setup & Installer v1.0.0" -ForegroundColor Cyan
Write-Host "  100% Offline AI Question Recognition & Solver Engine" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$installDir = Join-Path $env:LOCALAPPDATA "Programs\Rubric-Local"
$sourceDir = Join-Path $PSScriptRoot "dist\Rubric-Local"

if (-not (Test-Path $sourceDir)) {
    Write-Error "Build output not found at $sourceDir. Please run PyInstaller first."
    exit 1
}

# 1. Terminate running instances before overwrite
Write-Host "`n[*] Checking for active Rubric-Local instances..." -ForegroundColor Yellow
$activeProcesses = Get-Process -Name "Rubric-Local" -ErrorAction SilentlyContinue
if ($activeProcesses) {
    Write-Host "  [*] Closing running Rubric-Local process..." -ForegroundColor Yellow
    $activeProcesses | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# 2. Deploy application files
Write-Host "[*] Installing to $installDir..." -ForegroundColor Yellow
if (-not (Test-Path $installDir)) {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force
$icoSource = Join-Path $PSScriptRoot "rubric.ico"
if (Test-Path $icoSource) {
    Copy-Item -Path $icoSource -Destination $installDir -Force
}

# Copy uninstaller script to installation directory
$uninstallerScript = Join-Path $PSScriptRoot "uninstall.ps1"
if (Test-Path $uninstallerScript) {
    Copy-Item -Path $uninstallerScript -Destination $installDir -Force
}

Write-Host "  [+] Application files copied successfully." -ForegroundColor Green

# 3. Create Start Menu and Desktop Shortcuts
Write-Host "[*] Creating shortcuts..." -ForegroundColor Yellow
$exePath = Join-Path $installDir "Rubric-Local.exe"
$iconPath = Join-Path $installDir "rubric.ico"

$wshShell = New-Object -ComObject WScript.Shell

# Start Menu Shortcut
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startMenuLnk = Join-Path $startMenuDir "Rubric-Local.lnk"
$shortcut = $wshShell.CreateShortcut($startMenuLnk)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $installDir
$shortcut.Description = "Rubric-Local — 100% Offline AI Assistant"
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Save()
Write-Host "  [+] Start Menu shortcut created." -ForegroundColor Green

# Desktop Shortcut
$desktopDir = [System.Environment]::GetFolderPath("Desktop")
$desktopLnk = Join-Path $desktopDir "Rubric-Local.lnk"
$shortcutDesk = $wshShell.CreateShortcut($desktopLnk)
$shortcutDesk.TargetPath = $exePath
$shortcutDesk.WorkingDirectory = $installDir
$shortcutDesk.Description = "Rubric-Local — 100% Offline AI Assistant"
if (Test-Path $iconPath) {
    $shortcutDesk.IconLocation = "$iconPath,0"
}
$shortcutDesk.Save()
Write-Host "  [+] Desktop shortcut created." -ForegroundColor Green

# 4. Register in Windows Settings / Control Panel (Add/Remove Programs)
Write-Host "[*] Registering uninstaller with Windows Settings..." -ForegroundColor Yellow
$regKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\RubricLocal"
if (-not (Test-Path $regKey)) {
    New-Item -Path $regKey -Force | Out-Null
}

$uninstallCmd = "powershell.exe -ExecutionPolicy Bypass -NoProfile -File `"$installDir\uninstall.ps1`""

Set-ItemProperty -Path $regKey -Name "DisplayName" -Value "Rubric-Local"
Set-ItemProperty -Path $regKey -Name "DisplayVersion" -Value "1.0.0"
Set-ItemProperty -Path $regKey -Name "Publisher" -Value "Rubric-Local Open Source Project"
Set-ItemProperty -Path $regKey -Name "InstallLocation" -Value $installDir
Set-ItemProperty -Path $regKey -Name "DisplayIcon" -Value "$exePath,0"
Set-ItemProperty -Path $regKey -Name "UninstallString" -Value $uninstallCmd
Set-ItemProperty -Path $regKey -Name "NoModify" -Value 1 -Type DWord
Set-ItemProperty -Path $regKey -Name "NoRepair" -Value 1 -Type DWord

$totalSizeKB = [math]::Round((Get-ChildItem -Path $installDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1KB)
Set-ItemProperty -Path $regKey -Name "EstimatedSize" -Value $totalSizeKB -Type DWord

Write-Host "  [+] Windows Uninstaller registered cleanly." -ForegroundColor Green

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  INSTALLATION SUCCESSFUL!" -ForegroundColor Green
Write-Host "  You can launch Rubric-Local from:" -ForegroundColor Cyan
Write-Host "  • Start Menu -> Rubric-Local" -ForegroundColor Cyan
Write-Host "  • Desktop Shortcut" -ForegroundColor Cyan
Write-Host "  • $exePath" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
