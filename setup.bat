@echo off
echo =========================================================
echo  Bus Reservation System - Initial Setup Script
echo =========================================================
echo.

echo [1/2] Installing required Python dependencies...
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies. Please ensure Python and pip are installed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/2] Initializing database and demo records...
python seed.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Seeding failed.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo =========================================================
echo  SETUP COMPLETED SUCCESSFULLY!
echo  You can now start the application by running: run.bat
echo =========================================================
echo.
pause
