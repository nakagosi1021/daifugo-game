@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" lan_server.py
) else (
  python lan_server.py
)
pause
