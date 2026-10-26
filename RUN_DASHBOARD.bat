@echo off
title NAVAMESH Dashboard
cd /d "%~dp0"

set PY=python
where python >nul 2>nul || set PY=py
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python from python.org and tick "Add to PATH".
    pause
    exit /b 1
)

%PY% -c "import flask, cv2, numpy" >nul 2>nul
if errorlevel 1 (
    echo Installing required packages ^(first run only^)...
    %PY% -m pip install -r requirements.txt
)

echo Starting NAVAMESH Dashboard... your browser will open automatically.
%PY% server.py
echo.
echo Server stopped. If you saw an error above, copy it and send it over.
pause
