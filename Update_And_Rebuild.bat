@echo off
REM Batch file wrapper for Update_And_Rebuild.ps1

echo Starting FeedbackCollector Desktop Build...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0Update_And_Rebuild.ps1"

echo.
pause
