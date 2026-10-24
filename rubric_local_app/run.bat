@echo off
setlocal
cd /d "%~dp0"

:: Synchronize real AppData config with Windows Store Python LocalCache if present
for /d %%D in ("%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.*") do (
    if exist "%%D\LocalCache\Roaming\RubricLocal" (
        if exist "%APPDATA%\RubricLocal\config.json" (
            copy /y "%APPDATA%\RubricLocal\config.json" "%%D\LocalCache\Roaming\RubricLocal\config.json" >nul 2>&1
        )
    )
)

:: Verify Python runtime is reachable
where pythonw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pythonw rubric_local\app.py %*
    exit /b 0
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" python rubric_local\app.py %*
    exit /b 0
)

echo ========================================================
echo   [!] Rubric-Local Startup Error
echo   Python runtime was not detected in system PATH.
echo   Please install Python 3.10+ or run setup.ps1 first.
echo ========================================================
pause
exit /b 1

