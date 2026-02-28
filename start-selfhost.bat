@echo off
title Linkoader Backend + ngrok Tunnel
echo.
echo  ====================================
echo   Linkoader Self-Hosted Backend
echo  ====================================
echo.

:: --- Configuration ---
set BACKEND_DIR=%~dp0backend
set VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe
set PORT=8000

:: Check Python venv exists
if not exist "%VENV_PYTHON%" (
    echo [ERROR] Python venv not found at %VENV_PYTHON%
    echo         Run:  cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: Refresh PATH locally to ensure winget installations (like ngrok) are found
for /f "tokens=2*" %%A in ('reg query "HKLM\System\CurrentControlSet\Control\Session Manager\Environment" /v Path') do set "syspath=%%B"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "usrpath=%%B"
set "PATH=%syspath%;%usrpath%;%PATH%"

:: Check ngrok exists
where ngrok >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] ngrok not found. Install it:
    echo         winget install ngrok.ngrok
    pause
    exit /b 1
)

echo [1/2] Starting backend on port %PORT%...
start "Linkoader Backend" /min cmd /c "cd /d %BACKEND_DIR% && %VENV_PYTHON% -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%"

:: Wait for backend to start
timeout /t 3 /nobreak >nul

:: Verify backend is running
curl -s http://127.0.0.1:%PORT%/api/health >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Backend may still be starting... waiting 5 more seconds
    timeout /t 5 /nobreak >nul
)

echo [2/2] Starting ngrok Tunnel...

:: Read NGROK_DOMAIN from .env if it exists
set NGROK_DOMAIN=
if exist "%BACKEND_DIR%\.env" (
    for /f "tokens=1,2 delims==" %%a in (%BACKEND_DIR%\.env) do (
        if "%%a"=="NGROK_DOMAIN" set NGROK_DOMAIN=%%b
    )
)

echo.
if defined NGROK_DOMAIN (
    echo  Starting permanent tunnel on: https://%NGROK_DOMAIN%
    echo  -------------------------------------------------------------
    echo.
    ngrok http --domain=%NGROK_DOMAIN% %PORT%
) else (
    echo  Starting basic ephemeral tunnel...
    echo  Look for "Forwarding: https://your-domain.ngrok-free.app"
    echo  -------------------------------------------------------------
    echo.
    ngrok http %PORT%
)

:: If ngrok exits, also stop backend
echo.
echo Tunnel closed. Stopping backend...
taskkill /fi "WINDOWTITLE eq Linkoader Backend" /f >nul 2>&1
pause
