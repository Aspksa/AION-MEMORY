@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Python launcher missing. Install Python 3.11+ & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 (echo Failed to create virtual environment & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (echo Python dependency installation failed & pause & exit /b 1)
where npm.cmd >nul 2>nul
if errorlevel 1 (echo Node.js/npm missing & pause & exit /b 1)
pushd frontend
call npm.cmd install
if errorlevel 1 (popd & echo npm install failed & pause & exit /b 1)
start "AION UI" cmd /k "npm.cmd run dev"
popd
start "AION API" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"
timeout /t 4 >nul
start "" "http://127.0.0.1:5173"
echo AION MEMORY started. Close API and UI windows to stop.
