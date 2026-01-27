# =============================================================================
# START MAIN FLASK APPLICATION SCRIPT
# =============================================================================
# Purpose:      Restart only the Main Flask Application (app.py)
# Port:         5003
# Created:      2026-01-26
# Author:       Admin Service Enhancement
#
# Description:
#   This script provides a safe restart mechanism for the Main Flask Application
#   without affecting microservices. It handles port cleanup, process termination,
#   and application startup with proper error handling.
#
# Features:
#   - Kills existing processes on port 5003
#   - Active wait loop for port release (up to 10 seconds)
#   - Additional cleanup of related Python processes
#   - Starts app.py without creating new window
#   - Environment variable configuration for unbuffered output
#
# Usage:
#   .\start_main_app.ps1
#   Called by Admin Service restart functionality
#
# Integration:
#   - Triggered from Service Health Dashboard restart button
#   - Called via /api/services/main-app/restart endpoint
#   - Part of microservices management system
#
# Related Files:
#   - app.py (Main Flask Application)
#   - admin_service.py (Restart endpoint)
#   - templates/admin/health.html (Dashboard UI)
# =============================================================================

Write-Host "Starting Main Flask Application (Port 5003)..." -ForegroundColor Cyan

# Kill any existing process on port 5003
$processId = Get-NetTCPConnection -LocalPort 5003 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($processId) {
    Write-Host "Stopping existing process on port 5003..." -ForegroundColor Yellow
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    Write-Host "Waiting for port to be released..." -ForegroundColor Yellow
    
    # Wait for port to be fully released
    $maxWait = 10
    $waited = 0
    while ((Get-NetTCPConnection -LocalPort 5003 -ErrorAction SilentlyContinue) -and ($waited -lt $maxWait)) {
        Start-Sleep -Seconds 1
        $waited++
    }
    
    if ($waited -ge $maxWait) {
        Write-Host "Warning: Port may still be in use" -ForegroundColor Yellow
    } else {
        Write-Host "Port released successfully" -ForegroundColor Green
    }
}

# Additional cleanup - kill any python processes that might be holding the port
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -like "*5003*" -or $_.CommandLine -like "*app.py*" } | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 1

# Start the main Flask app
Write-Host "Starting app.py..." -ForegroundColor Green
$env:PYTHONUNBUFFERED = "1"
Start-Process python -ArgumentList "app.py" -NoNewWindow

Write-Host ""
Write-Host "Main Flask Application started on http://localhost:5003" -ForegroundColor Green
Write-Host ""
