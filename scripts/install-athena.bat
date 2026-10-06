@echo off
rem One-time setup: creates Athena's private Python environment (.venv) and installs
rem the free libraries it uses. Nothing is installed outside this folder.
title Install Athena
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" goto install

py -3.11 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 was not found. Install it from python.org, then run this again.
  pause
  exit /b 1
)
echo Creating Athena's Python environment...
py -3.11 -m venv .venv
if errorlevel 1 (
  echo Could not create the environment.
  pause
  exit /b 1
)

:install
echo Installing libraries (this takes a few minutes the first time)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements-local.txt
if errorlevel 1 (
  echo Installing failed. Check your internet connection and run this again.
  pause
  exit /b 1
)
echo.
echo Done. Start Athena with scripts\start-athena.bat
pause
