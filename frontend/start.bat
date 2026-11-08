@echo off
cd /d "%~dp0"
where npm >nul 2>nul || (echo Instaleaza Node.js de pe https://nodejs.org si apoi ruleaza din nou. & pause & exit /b)
if not exist node_modules (echo Prima pornire: instalez pachetele... & call npm install)
call npm run dev -- --open
pause
