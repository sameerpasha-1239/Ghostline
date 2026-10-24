@echo off
title Rubric-Local Developer Console
cd /d "%~dp0"
echo ========================================================
echo   Rubric-Local Developer Mode
echo   Console output, real-time logging, and diagnostics active
echo   Trigger Hotkey: Alt + /
echo ========================================================

:: Synchronize real AppData config with Windows Store Python LocalCache if present
for /d %%D in ("%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.*") do (
    if exist "%%D\LocalCache\Roaming\RubricLocal" (
        if exist "%APPDATA%\RubricLocal\config.json" (
            copy /y "%APPDATA%\RubricLocal\config.json" "%%D\LocalCache\Roaming\RubricLocal\config.json" >nul 2>&1
        )
    )
)

python rubric_local\app.py
pause
