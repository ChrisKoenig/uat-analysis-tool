<#
.SYNOPSIS
    Start the Triage Management API service.

.DESCRIPTION
    Launches the FastAPI-based Triage Management API on port 8009.
    This follows the same pattern as other start_*.ps1 scripts
    in the project.

.EXAMPLE
    .\start_triage.ps1
#>

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Triage Management API - Port 8009" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Docs:   http://localhost:8009/docs" -ForegroundColor Green
Write-Host "  ReDoc:  http://localhost:8009/redoc" -ForegroundColor Green
Write-Host "  Health: http://localhost:8009/health" -ForegroundColor Green
Write-Host ""

# Run from project root so 'triage' package is importable
Set-Location -Path $PSScriptRoot

python -m triage.triage_service
