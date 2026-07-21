@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" lan_client.py
) else (
  python lan_client.py
)
pause
