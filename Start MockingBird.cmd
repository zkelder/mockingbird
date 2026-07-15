@echo off
setlocal
cd /d "%~dp0"

if exist ".venv312\Scripts\python.exe" goto run_venv312
if exist ".venv\Scripts\python.exe" goto run_venv
goto run_python

:run_venv312
".venv312\Scripts\python.exe" -m mockingbird %*
goto finished

:run_venv
".venv\Scripts\python.exe" -m mockingbird %*
goto finished

:run_python
python -m mockingbird %*

:finished
set "MOCKINGBIRD_EXIT=%ERRORLEVEL%"
if not "%MOCKINGBIRD_EXIT%"=="0" pause
exit /b %MOCKINGBIRD_EXIT%
