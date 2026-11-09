@echo off
rem Porneste serverul API (python -m server). Optiuni: start-server.bat --fresh / --mode camera ...
cd /d "%~dp0"
where python >nul 2>nul || (echo Instaleaza Python de pe https://www.python.org si apoi ruleaza din nou. & pause & exit /b)
python -c "import fastapi, uvicorn" 2>nul || (echo Prima pornire: instalez pachetele... & python -m pip install -r requirements-server.txt)
python -m server %*
pause
