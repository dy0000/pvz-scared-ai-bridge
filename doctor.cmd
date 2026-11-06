@echo off
"%~dp0.venv\Scripts\python.exe" -X utf8 "%~dp0scripts\doctor.py" %*
if errorlevel 1 (pause & exit /b 1)
pause
