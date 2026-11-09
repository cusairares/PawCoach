@echo off
title PawCoach App
cd /d "%~dp0"

echo ========================================================
echo                   Starting PawCoach
echo ========================================================
echo.

rem 1. Check Python and Node.js
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python nu este instalat sau nu este in PATH!
    echo Descarca Python de pe: https://www.python.org
    pause
    exit /b 1
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js nu este instalat sau nu este in PATH!
    echo Descarca Node.js de pe: https://nodejs.org
    pause
    exit /b 1
)

rem 2. Install backend dependencies if missing
python -c "import fastapi, uvicorn" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Se instaleaza dependintele Python...
    python -m pip install -r requirements-server.txt
)

rem 3. Install frontend dependencies if missing
if not exist "frontend\node_modules" (
    echo [INFO] Se instaleaza dependintele Frontend...
    cd frontend
    call npm install
    cd /d "%~dp0"
)

echo.
echo [1/2] Se porneste serverul backend pe portul 8000...
start "PawCoach Backend Server (Port 8000)" cmd /k "cd /d ""%~dp0"" && python -m server %*"

rem Asteapta scurt ca serverul backend sa initializeze
ping 127.0.0.1 -n 3 >nul

echo [2/2] Se porneste frontend-ul si se deschide aplicatia in browser...
cd /d "%~dp0frontend"
call npm run dev -- --open

echo.
echo Aplicatia a fost oprita.
pause
