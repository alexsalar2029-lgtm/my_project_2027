@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
python local_ai.py test
set "LOCAL_AI_EXIT=%errorlevel%"
pause
exit /b %LOCAL_AI_EXIT%
