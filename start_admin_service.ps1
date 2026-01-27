# Admin Service Startup Script
# Runs on port 8008 (moved from 8004 to avoid conflict with UAT Management)

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Admin Service - Startup Script" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Setting up authentication..." -ForegroundColor Yellow
# Uncomment next line ONLY when deploying to Azure:
# $env:AZURE_CLIENT_ID = "7846e03e-9279-4057-bdcd-4a2f7f8ebe85"
Write-Host "   Using local Azure CLI authentication" -ForegroundColor Gray

Write-Host "`n[2/3] Loading configuration from Key Vault..." -ForegroundColor Yellow
Write-Host "   Secrets will be loaded from Azure Key Vault" -ForegroundColor Gray

Write-Host "`n[3/3] Starting Admin Service on port 8008..." -ForegroundColor Yellow
Write-Host "   This service provides administrative tools for:" -ForegroundColor Gray
Write-Host "   - Evaluation data viewer and search" -ForegroundColor Gray
Write-Host "   - System statistics and analytics" -ForegroundColor Gray
Write-Host "   - User management (future)" -ForegroundColor Gray
Write-Host "   - Configuration management (future)" -ForegroundColor Gray

Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "Admin Service URLs:" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Dashboard:          http://localhost:8008/" -ForegroundColor White
Write-Host "  Evaluations List:   http://localhost:8008/evaluations" -ForegroundColor White
Write-Host "  Interactive Viewer: http://localhost:8008/evaluations/viewer" -ForegroundColor White
Write-Host "  API Search:         http://localhost:8008/api/evaluations/search" -ForegroundColor White
Write-Host "  API Export:         http://localhost:8008/api/evaluations/export" -ForegroundColor White
Write-Host "================================================================================" -ForegroundColor Cyan

Write-Host "`nStarting Flask application..." -ForegroundColor Yellow
Write-Host ""

# Set Python unbuffered for real-time output
$env:PYTHONUNBUFFERED = "1"

# Run the admin service
python admin_service.py
