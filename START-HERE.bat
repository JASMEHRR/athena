@echo off
title Athena overnight build
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0run-overnight.ps1" %*
echo.
pause
