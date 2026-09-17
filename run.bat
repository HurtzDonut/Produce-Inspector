@echo off

REM This script sets up a Python virtual environment in a temporary directory
REM and opens a new command session within it. When the command session ends,
REM the script deletes the virtual environment.

SETLOCAL

REM Note, ran into issues using built-in %RANDOM% bat variable.
REM When multiple instances of this script were launched at same time, it wasn't so random. :- )
REM Switching over to using powershell's Get-Random commandlet.
set "psCommand=powershell -NoProfile -Command ^(Get-Random -Minimum 10000 -Maximum 99999^)"
for /f %%i in ('%psCommand%' ) do set "randomNumber=%%i"
set NAME=venv_%randomNumber%
set VENV=%TEMP%%NAME%
set PYTHON=python
set ERROR_CODE=1

echo Creating/Activating new virtual environment for Python in %VENV% ...
%PYTHON% -m venv %VENV% || echo -- venv failed && exit /b %ERROR_CODE%
call %VENV%\Scripts\activate.bat || echo -- activate failed && exit /b %ERROR_CODE%

echo Installing project dependencies ...
pip install -r %~dp0requirements.txt || echo -- dependencies install failed && exit /b %ERROR_CODE%

echo Virtual environment will be cleared upon exit ...
echo Running script ...

%PYTHON% -u %~dp0produce_inspector.py || echo -- script execution failed && exit /b %ERROR_CODE%

echo Deleting virtual environment: %VENV%
call deactivate
timeout /t 20 /nobreak >nul
rmdir /s /q %VENV%