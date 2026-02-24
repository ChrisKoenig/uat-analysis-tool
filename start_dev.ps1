# ============================================================================
# GCS Development Startup - Clean Start All Services
# ============================================================================
#
# Starts all 4 services required for local development:
#   - Triage API        (port 8009)  - FastAPI backend
#   - Field Portal API  (port 8010)  - FastAPI backend
#   - Triage UI         (port 3000)  - Vite dev server
#   - Field Portal UI   (port 3001)  - Vite dev server
#
# Usage:
#   .\start_dev.ps1            - Start everything
#   .\start_dev.ps1 -SkipUI    - APIs only (UIs already running)
#   .\start_dev.ps1 -SkipAPI   - UIs only  (APIs already running)
#
# ============================================================================

param(
    [switch]$SkipUI,
    [switch]$SkipAPI
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  GCS Development Environment - Clean Start" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "================================================================================" -ForegroundColor Cyan

# -- Step 1: Kill existing processes -----------------------------------------------

Write-Host "`n[1/5] Cleaning up existing processes..." -ForegroundColor Yellow

# Kill Python processes (APIs)
$pyProcs = Get-Process -Name python -ErrorAction SilentlyContinue
if ($pyProcs) {
    Write-Host "  Stopping $($pyProcs.Count) Python process(es)..." -ForegroundColor Gray
    $pyProcs | Stop-Process -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "  No Python processes running" -ForegroundColor Gray
}

# Kill Node processes on our ports (Vite dev servers)
foreach ($port in @(3000, 3001)) {
    $listening = netstat -ano | Select-String "LISTENING" | Select-String ":$port "
    if ($listening) {
        $pid = ($listening -split '\s+')[-1]
        if ($pid -and $pid -match '^\d+$') {
            Write-Host "  Stopping process on port $port (PID $pid)..." -ForegroundColor Gray
            Stop-Process -Id ([int]$pid) -Force -ErrorAction SilentlyContinue
        }
    }
}

Start-Sleep -Seconds 3

# Verify ports are free
$busy = @()
foreach ($port in @(8009, 8010, 3000, 3001)) {
    $check = netstat -ano | Select-String "LISTENING" | Select-String ":$port "
    if ($check) { $busy += $port }
}
if ($busy.Count -gt 0) {
    Write-Host "  WARNING: Ports still in use: $($busy -join ', ')" -ForegroundColor Red
    Write-Host "  Waiting 5 more seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
} else {
    Write-Host "  All ports free" -ForegroundColor Green
}

# -- Step 2: Set environment variables ---------------------------------------------

Write-Host "`n[2/5] Setting environment variables..." -ForegroundColor Yellow

$env:COSMOS_ENDPOINT    = "https://cosmos-gcs-dev.documents.azure.com:443/"
$env:COSMOS_USE_AAD     = "true"
$env:COSMOS_TENANT_ID   = "16b3c013-d300-468d-ac64-7eda0820b6d3"
$env:PYTHONIOENCODING   = "utf-8"
$env:PYTHONPATH         = $Root

# Azure OpenAI (workaround while Key Vault public access is disabled)
$env:AZURE_OPENAI_ENDPOINT = "https://openai-bp-northcentral.openai.azure.com/"
$env:AZURE_OPENAI_USE_AAD  = "true"

# Application Insights (telemetry for both APIs)
$env:APPLICATIONINSIGHTS_CONNECTION_STRING = "InstrumentationKey=59506f54-8a7a-4c57-b26c-ed2a0dc7daae;IngestionEndpoint=https://northcentralus-0.in.applicationinsights.azure.com/;LiveEndpoint=https://northcentralus.livediagnostics.monitor.azure.com/;ApplicationId=6a7da292-a8af-4742-9af7-cd7909178530"

Write-Host "  COSMOS_ENDPOINT  = $env:COSMOS_ENDPOINT" -ForegroundColor Gray
Write-Host "  COSMOS_USE_AAD   = $env:COSMOS_USE_AAD" -ForegroundColor Gray
Write-Host "  AZURE_OPENAI     = $env:AZURE_OPENAI_ENDPOINT" -ForegroundColor Gray
Write-Host "  APP_INSIGHTS     = (configured)" -ForegroundColor Gray
Write-Host "  PYTHONPATH       = $Root" -ForegroundColor Gray

# -- Step 3: Start APIs --------------------------------------------------------

if (-not $SkipAPI) {
    Write-Host "`n[3/5] Starting API services..." -ForegroundColor Yellow

    # Triage API (port 8009)
    Write-Host "  Starting Triage API on port 8009..." -ForegroundColor Cyan
    $triageApi = Start-Process -PassThru -NoNewWindow -FilePath python -ArgumentList @(
        "-m", "uvicorn", "triage.api.routes:app",
        "--host", "0.0.0.0", "--port", "8009", "--reload"
    ) -WorkingDirectory $Root
    Write-Host "    PID: $($triageApi.Id)" -ForegroundColor DarkGray

    Start-Sleep -Seconds 3

    # Field Portal API (port 8010)
    Write-Host "  Starting Field Portal API on port 8010..." -ForegroundColor Cyan
    $fieldApi = Start-Process -PassThru -NoNewWindow -FilePath python -ArgumentList @(
        "-m", "uvicorn", "field-portal.api.main:app",
        "--host", "0.0.0.0", "--port", "8010", "--reload"
    ) -WorkingDirectory $Root
    Write-Host "    PID: $($fieldApi.Id)" -ForegroundColor DarkGray

    # Wait for APIs to initialize
    Write-Host "  Waiting for APIs to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds 8

    # Health checks
    foreach ($svc in @(
        @{ Name = "Triage API";       Url = "http://localhost:8009/health" },
        @{ Name = "Field Portal API"; Url = "http://localhost:8010/health" }
    )) {
        try {
            $null = Invoke-WebRequest -Uri $svc.Url -Method GET -UseBasicParsing -TimeoutSec 5
            Write-Host "  $($svc.Name): HEALTHY" -ForegroundColor Green
        } catch {
            Write-Host "  $($svc.Name): May still be starting..." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "`n[3/5] Skipping APIs (-SkipAPI)" -ForegroundColor DarkGray
}

# -- Step 4: Start UIs ---------------------------------------------------------

if (-not $SkipUI) {
    Write-Host "`n[4/5] Starting UI dev servers..." -ForegroundColor Yellow

    # Triage UI (port 3000)
    Write-Host "  Starting Triage UI on port 3000..." -ForegroundColor Cyan
    $triageUi = Start-Process -PassThru -NoNewWindow -FilePath npm -ArgumentList "run", "dev" `
        -WorkingDirectory "$Root\triage-ui"
    Write-Host "    PID: $($triageUi.Id)" -ForegroundColor DarkGray

    Start-Sleep -Seconds 2

    # Field Portal UI (port 3001)
    Write-Host "  Starting Field Portal UI on port 3001..." -ForegroundColor Cyan
    $fieldUi = Start-Process -PassThru -NoNewWindow -FilePath npm -ArgumentList "run", "dev" `
        -WorkingDirectory "$Root\field-portal\ui"
    Write-Host "    PID: $($fieldUi.Id)" -ForegroundColor DarkGray

    Start-Sleep -Seconds 5
} else {
    Write-Host "`n[4/5] Skipping UIs (-SkipUI)" -ForegroundColor DarkGray
}

# -- Step 5: Summary -----------------------------------------------------------

Write-Host "`n[5/5] Verifying services..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

$services = @(
    @{ Name = "Triage API";       Port = 8009; Url = "http://localhost:8009" },
    @{ Name = "Field Portal API"; Port = 8010; Url = "http://localhost:8010" },
    @{ Name = "Triage UI";        Port = 3000; Url = "http://localhost:3000" },
    @{ Name = "Field Portal UI";  Port = 3001; Url = "http://localhost:3001" }
)

Write-Host ""
Write-Host "  Service                Port    Status" -ForegroundColor White
Write-Host "  ---------------------  ------  ------" -ForegroundColor DarkGray

foreach ($svc in $services) {
    $listening = netstat -ano | Select-String "LISTENING" | Select-String ":$($svc.Port) "
    if ($listening) {
        $pid = ($listening -split '\s+')[-1]
        Write-Host "  $($svc.Name.PadRight(23)) :$($svc.Port)   " -NoNewline -ForegroundColor White
        Write-Host "UP" -NoNewline -ForegroundColor Green
        Write-Host "  (PID $pid)" -ForegroundColor DarkGray
    } else {
        Write-Host "  $($svc.Name.PadRight(23)) :$($svc.Port)   " -NoNewline -ForegroundColor White
        Write-Host "DOWN" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Triage Admin Portal:  http://localhost:3000" -ForegroundColor White
Write-Host "  Field Portal:         http://localhost:3001" -ForegroundColor White
Write-Host "  Triage API Docs:      http://localhost:8009/docs" -ForegroundColor DarkGray
Write-Host "  Field Portal API Docs: http://localhost:8010/docs" -ForegroundColor DarkGray
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
