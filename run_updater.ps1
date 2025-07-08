# AI Documentation Auto-Updater - Windows Scheduler Script
# Run this daily to check for documentation updates

param(
    [switch]$UpdateOriginals = $false,
    [switch]$SummaryOnly = $false,
    [string]$ConfigPath = "config.json"
)

# Set working directory to script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Create log directory if it doesn't exist
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Set log file with timestamp
$LogFile = "logs\doc_updater_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

Write-Host "Starting AI Documentation Update Check..." -ForegroundColor Green
Write-Host "Log file: $LogFile" -ForegroundColor Yellow

try {
    # Check if Python is available
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $PythonCmd) {
        Write-Error "Python not found. Please install Python and add it to PATH."
        exit 1
    }

    # Check if virtual environment exists, create if not
    if (!(Test-Path "venv")) {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
        python -m venv venv
    }

    # Activate virtual environment
    & "venv\Scripts\Activate.ps1"

    # Install/update requirements
    Write-Host "Installing/updating requirements..." -ForegroundColor Yellow
    pip install -r requirements.txt --quiet

    # Prepare arguments
    $Args = @()
    if ($UpdateOriginals) { $Args += "--update-originals" }
    if ($SummaryOnly) { $Args += "--summary-only" }
    if ($ConfigPath) { $Args += @("--config", $ConfigPath) }

    # Run the updater
    Write-Host "Running documentation updater..." -ForegroundColor Green
    $Output = python doc_updater.py @Args 2>&1

    # Log output
    $Output | Out-File -FilePath $LogFile -Encoding UTF8
    
    # Display output
    Write-Host $Output

    # Check for updates and send notifications if configured
    if ($Output -match "documents updated:") {
        Write-Host "Updates detected! Check the versions folder for new versions." -ForegroundColor Yellow
        
        # Optional: Send email notification (requires configuration)
        # Send-MailMessage -To "you@example.com" -Subject "AI Docs Updated" -Body $Output
    } else {
        Write-Host "No updates needed. All documentation is current." -ForegroundColor Green
    }

} catch {
    $ErrorMsg = "Error running doc updater: $_"
    Write-Error $ErrorMsg
    $ErrorMsg | Out-File -FilePath $LogFile -Append -Encoding UTF8
    exit 1
} finally {
    # Deactivate virtual environment
    deactivate
}

Write-Host "Documentation update check completed." -ForegroundColor Green
