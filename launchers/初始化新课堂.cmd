@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
"%~dp0runtime\python\python.exe" -B "%~dp0app\prepare_installation.py" --new --destination "%~dp0data" --friendly
set "init_result=%ERRORLEVEL%"
echo.
pause
exit /b %init_result%
