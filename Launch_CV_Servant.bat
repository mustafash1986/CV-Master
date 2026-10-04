@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   CV Servant - Smart Job Agent
echo   Eng. Mustafa Mahmoud Shawky
echo ========================================================
echo.

set "PY_EXE="

if exist "C:\Python314\python.exe" (
    set "PY_EXE=C:\Python314\python.exe"
    goto found_py
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_EXE=python"
    goto found_py
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    set "PY_EXE=py"
    goto found_py
)

echo [ERROR] Python not found on this machine!
pause
exit /b 1

:found_py
echo Starting CV Servant via: %PY_EXE%
echo.
"%PY_EXE%" run_app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application closed with code: %errorlevel%
    pause
)
