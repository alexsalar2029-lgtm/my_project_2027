@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
where py >nul 2>nul
if errorlevel 1 (
  set "SHOP_PY=python"
) else (
  set "SHOP_PY=py -3"
)
%SHOP_PY% server.py start
if errorlevel 1 goto failed
exit /b 0
:failed
echo Python 3.11+ is required. Review the error above.
pause
