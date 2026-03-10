<#
.SYNOPSIS
    Stops all locally running GCS services (APIs + UIs).

.DESCRIPTION
    Kills Python processes (Triage API, Field Portal API) and Node/Vite
    processes on the dev server ports.  Use this when you want to fully
    shut everything down and stop authentication prompts.

.EXAMPLE
    .\infra\scripts\stop-services.ps1
#>

$ErrorActionPreference = "Continue"

$ports = @(8009, 8010, 3000, 3001)

Write-Host ""
Write-Host "  Stopping GCS services..." -ForegroundColor Yellow
Write-Host ""

$stopped = 0

# ── Kill processes listening on service ports ────────────────────────────────
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        $pid = $conn.OwningProcess
        $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Port $port  PID $pid  ($($proc.ProcessName)) — stopping" -ForegroundColor Cyan
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            $stopped++
        }
    }
}

# ── Kill any remaining Python uvicorn workers (child processes) ──────────────
$uvicornProcs = Get-Process -Name python -ErrorAction SilentlyContinue |
Where-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        $cmdLine -and $cmdLine -match 'uvicorn'
    }
    catch { $false }
}

foreach ($proc in $uvicornProcs) {
    Write-Host "  Uvicorn worker PID $($proc.Id) — stopping" -ForegroundColor Cyan
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    $stopped++
}

# ── Verify ───────────────────────────────────────────────────────────────────
Start-Sleep -Seconds 1

$still = @()
foreach ($port in $ports) {
    $check = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($check) { $still += $port }
}

Write-Host ""
if ($still.Count -gt 0) {
    Write-Host "  WARNING: Ports still in use: $($still -join ', ')" -ForegroundColor Red
}
elseif ($stopped -eq 0) {
    Write-Host "  No running services found." -ForegroundColor DarkGray
}
else {
    Write-Host "  All services stopped ($stopped process(es) killed)." -ForegroundColor Green
}
Write-Host ""
