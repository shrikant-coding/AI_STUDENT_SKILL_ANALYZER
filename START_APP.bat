@echo off
setlocal
cd /d "%~dp0"
title SkillPath AI - Setup and Launch

echo ================================================
echo       SKILLPATH AI - FIRST TIME SETUP
echo ================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found. Install Python 3.10 or newer and enable "Add Python to PATH".
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 goto :error
)

call "venv\Scripts\activate.bat"
echo Installing required packages. This may take a few minutes on first launch...
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not defined FLASK_SECRET_KEY set "FLASK_SECRET_KEY=replace-this-with-a-long-random-secret-before-sharing"
if not defined SKILLPATH_ADMIN_EMAIL set "SKILLPATH_ADMIN_EMAIL=admin@skillpath.local"
if not defined SKILLPATH_ADMIN_PASSWORD set "SKILLPATH_ADMIN_PASSWORD=Admin@12345"

echo.
echo Starting SkillPath AI...
echo Student app: http://127.0.0.1:5000
echo Admin panel: http://127.0.0.1:5000/admin/login
echo Default admin email: %SKILLPATH_ADMIN_EMAIL%
echo Default admin password: %SKILLPATH_ADMIN_PASSWORD%
echo Keep this window open while using the app.
start "" cmd /c "timeout /t 3 /nobreak ^>nul ^& start http://127.0.0.1:5000"
python app.py

goto :eof

:error
echo.
echo Setup failed. Check your internet connection and Python installation, then run this file again.
pause
exit /b 1
