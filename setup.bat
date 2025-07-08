@echo off
REM Setup script for AI Documentation Auto-Updater

echo.
echo ========================================
echo AI Documentation Auto-Updater Setup
echo ========================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    echo.
    pause
    exit /b 1
)

echo Python is installed.
echo.

echo Creating virtual environment...
if exist "venv" (
    echo Virtual environment already exists, using existing one.
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully.
)
echo.

echo Activating virtual environment and installing packages...
call venv\Scripts\activate.bat

echo Installing required packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install packages
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit config.json and add your API keys
echo 2. Run 'run_updater.bat' to start using the updater
echo.
echo API Keys needed:
echo - OpenAI API Key (from https://platform.openai.com/api-keys)
echo - Anthropic API Key (from https://console.anthropic.com/)
echo.
echo The config.json file will open now for editing...
echo.
pause

REM Try to open config.json in VS Code, or notepad as fallback
code config.json 2>nul || notepad config.json

echo.
echo Setup completed successfully!
pause
