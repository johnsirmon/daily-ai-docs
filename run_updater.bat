@echo off
REM AI Documentation Auto-Updater - Simple Batch Launcher
REM This batch file makes it easy to run the updater

echo.
echo ========================================
echo AI Documentation Auto-Updater
echo ========================================
echo.

REM Check if config.json exists
if not exist "config.json" (
    echo [ERROR] config.json not found!
    echo Please run setup.bat first or ensure config.json exists.
    echo.
    pause
    exit /b 1
)

REM Ask user what they want to do
echo Choose an option:
echo [1] Check for updates (create versions only)
echo [2] Check and update original files
echo [3] Show summary of last check
echo [4] Setup/Install requirements
echo [0] Exit
echo.
set /p choice="Enter your choice (0-4): "

if "%choice%"=="1" (
    echo.
    echo Running update check (versions only)...
    powershell -ExecutionPolicy Bypass -File "run_updater.ps1"
) else if "%choice%"=="2" (
    echo.
    echo Running update check (will update original files)...
    powershell -ExecutionPolicy Bypass -File "run_updater.ps1" -UpdateOriginals
) else if "%choice%"=="3" (
    echo.
    echo Showing summary of last check...
    powershell -ExecutionPolicy Bypass -File "run_updater.ps1" -SummaryOnly
) else if "%choice%"=="4" (
    echo.
    echo Setting up environment...
    call setup.bat
) else if "%choice%"=="0" (
    echo Exiting...
    exit /b 0
) else (
    echo Invalid choice. Please try again.
    echo.
    pause
    goto :eof
)

echo.
echo Operation completed. Check the output above.
echo.
pause
