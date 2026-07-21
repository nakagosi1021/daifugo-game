@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  ".venv\Scripts\pythonw.exe" lan_launcher.pyw
) else if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" lan_launcher.pyw
) else (
  python lan_launcher.pyw
)
