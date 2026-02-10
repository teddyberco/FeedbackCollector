@echo off
echo Starting FeedbackCollector Desktop Build...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0Build.ps1"
echo.
pause
