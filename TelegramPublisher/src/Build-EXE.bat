@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .build-env
if errorlevel 1 goto failure
.build-env\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto failure
.build-env\Scripts\python.exe build_windows.py
if errorlevel 1 goto failure
echo Ready: dist\TelegramPublisher.exe
pause
exit /b 0
:failure
echo Build failed. Read the error above.
pause
exit /b 1
