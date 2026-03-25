@echo off
title IDS - Startup

echo ============================================================
echo   Network IDS - Quick Start
echo ============================================================
echo.

:: --- 1. Check environment ---
echo [1/5] Checking environment...

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo     %%i

where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo     Node.js %%i

echo     Environment OK
echo.

:: --- 2. Install backend dependencies ---
echo [2/5] Installing backend dependencies...
pushd "%~dp0backend"
python -m pip install -r requirements.txt -q
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install backend dependencies
    popd
    pause
    exit /b 1
)
popd
echo     Backend dependencies ready
echo.

:: --- 3. Install frontend dependencies ---
echo [3/5] Installing frontend dependencies...
pushd "%~dp0frontend"
if not exist node_modules (
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install frontend dependencies
        popd
        pause
        exit /b 1
    )
) else (
    echo     node_modules already exists, skipping
)
popd
echo     Frontend dependencies ready
echo.

:: --- 4. Start backend ---
echo [4/5] Starting backend (http://localhost:8000) ...
pushd "%~dp0backend"
start "IDS-Backend" cmd /k "title IDS-Backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
popd
echo     Backend started in new window
echo.

:: --- 5. Start frontend ---
echo [5/5] Starting frontend (http://localhost:5173) ...
pushd "%~dp0frontend"
start "IDS-Frontend" cmd /k "title IDS-Frontend && npx vite --host"
popd
echo     Frontend started in new window
echo.

echo ============================================================
echo   Done!
echo   Backend API:  http://localhost:8000/docs
echo   Frontend:     http://localhost:5173
echo ============================================================
echo.
echo Press any key to close this window...
pause >nul
