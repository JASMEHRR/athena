@echo off
rem Starts Athena: loads the latest lessons, backs up your progress, opens the app.
rem Close this window to stop Athena.
title Athena
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo Athena is not set up on this PC yet.
  echo Double-click scripts\install-athena.bat first, then run this again.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m athena.importer
if errorlevel 1 (
  echo.
  echo Athena could not load its lessons. The message above says why.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m athena.backup
".venv\Scripts\python.exe" -m athena.server %*
if errorlevel 1 pause
