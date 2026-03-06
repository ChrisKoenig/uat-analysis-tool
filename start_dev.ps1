# ============================================================================
# GCS Startup - Clean Start All Services
# ============================================================================
#
# Starts all 4 services required for local development:
#   - Triage API        (port 8009)  - FastAPI backend
#   - Field Portal API  (port 8010)  - FastAPI backend
#   - Triage UI         (port 3000)  - Vite dev server
#   - Field Portal UI   (port 3001)  - Vite dev server
#
# Usage:
#   .\start_dev.ps1                         - Start with dev config (default)
#   .\start_dev.ps1 -Environment preprod    - Start with preprod config
#   .\start_dev.ps1 -Env preprod            - Same (short alias)
#   .\start_dev.ps1 -SkipUI                 - APIs only (UIs already running)
#   .\start_dev.ps1 -SkipAPI                - UIs only  (APIs already running)
#   .\start_dev.ps1 -Env preprod -SkipUI
#
# ============================================================================

param(
    [Alias("Env")]
    [string]$Environment = "dev",
    [switch]$SkipUI,
    [switch]$SkipAPI
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot

$_envColor = switch ($Environment) { "dev" { "Cyan" } "preprod" { "Yellow" } "prod" { "Green" } default { "White" } }

Write-Host ""
Write-Host "================================================================================" -ForegroundColor $_envColor
Write-Host "  GCS Environment Startup ($Environment)" -ForegroundColor $_envColor
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "================================================================================" -ForegroundColor $_envColor

# -- Step 1: Kill existing processes -----------------------------------------------

Write-Host "`n[1/6] Cleaning up existing processes..." -ForegroundColor Yellow

# Kill Python processes (APIs)
$pyProcs = Get-Process -Name python -ErrorAction SilentlyContinue
if ($pyProcs) {
    Write-Host "  Stopping $($pyProcs.Count) Python process(es)..." -ForegroundColor Gray
    $pyProcs | Stop-Process -Force -ErrorAction SilentlyContinue
}
else {
    Write-Host "  No Python processes running" -ForegroundColor Gray
}

# Kill Node processes on our ports (Vite dev servers)
foreach ($port in @(3000, 3001)) {
    $listening = netstat -ano | Select-String "LISTENING" | Select-String ":$port "
    if ($listening) {
        $procId = ($listening -split '\s+')[-1]
        if ($procId -and $procId -match '^\d+$') {
            Write-Host "  Stopping process on port $port (PID $procId)..." -ForegroundColor Gray
            Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
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
}
else {
    Write-Host "  All ports free" -ForegroundColor Green
}

# -- Step 2: Load config & set environment variables -----------------------------------

Write-Host "`n[2/6] Loading config & setting environment variables..." -ForegroundColor Yellow

# Load config from the shared JSON (single source of truth)
$env:APP_ENV = $Environment
$_configJsonPath = Join-Path $Root "config\environments\$Environment.json"
. (Join-Path $Root "config\environments\_load-config.ps1")

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = $Root

Write-Host "  APP_ENV          = $Environment" -ForegroundColor Gray
Write-Host "  Cosmos Account   = $COSMOS_ACCOUNT" -ForegroundColor Gray
Write-Host "  OpenAI Account   = $OPENAI_ACCOUNT" -ForegroundColor Gray
Write-Host "  Key Vault        = $KV_NAME" -ForegroundColor Gray
Write-Host "  PYTHONPATH       = $Root" -ForegroundColor Gray

# -- Step 3: Write local UI config -------------------------------------------------

Write-Host "`n[3/6] Writing local UI configs (config.local.json -> config.json)..." -ForegroundColor Yellow

$uiConfigs = @(
    @{ Label = "Triage UI"; Dir = "$Root\triage-ui\public" },
    @{ Label = "Field Portal UI"; Dir = "$Root\field-portal\ui\public" }
)
foreach ($ui in $uiConfigs) {
    $src = Join-Path $ui.Dir "config.local.json"
    $dest = Join-Path $ui.Dir "config.json"
    if (Test-Path $src) {
        Copy-Item $src $dest -Force
        Write-Host "  $($ui.Label): config.json <- config.local.json" -ForegroundColor Green
    }
    else {
        Write-Host "  $($ui.Label): config.local.json NOT FOUND - skipped" -ForegroundColor Red
    }
}

# -- Step 4: Start APIs --------------------------------------------------------

if (-not $SkipAPI) {
    Write-Host "`n[4/6] Starting API services..." -ForegroundColor Yellow

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
            @{ Name = "Triage API"; Url = "http://localhost:8009/health" },
            @{ Name = "Field Portal API"; Url = "http://localhost:8010/health" }
        )) {
        try {
            $null = Invoke-WebRequest -Uri $svc.Url -Method GET -UseBasicParsing -TimeoutSec 5
            Write-Host "  $($svc.Name): HEALTHY" -ForegroundColor Green
        }
        catch {
            Write-Host "  $($svc.Name): May still be starting..." -ForegroundColor Yellow
        }
    }
}
else {
    Write-Host "`n[4/6] Skipping APIs (-SkipAPI)" -ForegroundColor DarkGray
}

# -- Step 4: Start UIs ---------------------------------------------------------

if (-not $SkipUI) {
    Write-Host "`n[5/6] Starting UI dev servers..." -ForegroundColor Yellow

    # Triage UI (port 3000)
    Write-Host "  Starting Triage UI on port 3000..." -ForegroundColor Cyan
    $triageUi = Start-Process -PassThru -NoNewWindow -FilePath cmd.exe -ArgumentList "/c", "npm", "run", "dev" `
        -WorkingDirectory "$Root\triage-ui"
    Write-Host "    PID: $($triageUi.Id)" -ForegroundColor DarkGray

    Start-Sleep -Seconds 2

    # Field Portal UI (port 3001)
    Write-Host "  Starting Field Portal UI on port 3001..." -ForegroundColor Cyan
    $fieldUi = Start-Process -PassThru -NoNewWindow -FilePath cmd.exe -ArgumentList "/c", "npm", "run", "dev" `
        -WorkingDirectory "$Root\field-portal\ui"
    Write-Host "    PID: $($fieldUi.Id)" -ForegroundColor DarkGray

    Start-Sleep -Seconds 5
}
else {
    Write-Host "`n[5/6] Skipping UIs (-SkipUI)" -ForegroundColor DarkGray
}

# -- Step 5: Summary -----------------------------------------------------------

Write-Host "`n[6/6] Verifying services..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

$services = @(
    @{ Name = "Triage API"; Port = 8009; Url = "http://localhost:8009" },
    @{ Name = "Field Portal API"; Port = 8010; Url = "http://localhost:8010" },
    @{ Name = "Triage UI"; Port = 3000; Url = "http://localhost:3000" },
    @{ Name = "Field Portal UI"; Port = 3001; Url = "http://localhost:3001" }
)

Write-Host ""
Write-Host "  Service                Port    Status" -ForegroundColor White
Write-Host "  ---------------------  ------  ------" -ForegroundColor DarkGray

foreach ($svc in $services) {
    $listening = netstat -ano | Select-String "LISTENING" | Select-String ":$($svc.Port) "
    if ($listening) {
        $procId = ($listening -split '\s+')[-1]
        Write-Host "  $($svc.Name.PadRight(23)) :$($svc.Port)   " -NoNewline -ForegroundColor White
        Write-Host "UP" -NoNewline -ForegroundColor Green
        Write-Host "  (PID $procId)" -ForegroundColor DarkGray
    }
    else {
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
