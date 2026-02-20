# START BOTH UIs FOR SIDE-BY-SIDE COMPARISON
# ===========================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "SIDE-BY-SIDE COMPARISON SETUP" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Step 1: Check if microservices are running
Write-Host "📋 Step 1: Checking microservices status..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -Method GET -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✅ Microservices are running!" -ForegroundColor Green
} catch {
    Write-Host "❌ Microservices are NOT running!" -ForegroundColor Red
    Write-Host "⚠️  Please start microservices first:" -ForegroundColor Yellow
    Write-Host "   .\start_all_services.ps1`n" -ForegroundColor White
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 2: Start original Flask app (port 5002)
Write-Host "`n📋 Step 2: Starting ORIGINAL Flask app (port 5002)..." -ForegroundColor Yellow
$originalApp = Start-Process powershell -ArgumentList "-NoExit", "-Command", "python app.py" -PassThru -WindowStyle Normal
Write-Host "✅ Original app starting... (PID: $($originalApp.Id))" -ForegroundColor Green
Start-Sleep -Seconds 2

# Step 3: Start microservices Flask app (port 5003)
Write-Host "`n📋 Step 3: Starting MICROSERVICES Flask app (port 5003)..." -ForegroundColor Yellow
$microservicesApp = Start-Process powershell -ArgumentList "-NoExit", "-Command", "python app_microservices.py" -PassThru -WindowStyle Normal
Write-Host "✅ Microservices app starting... (PID: $($microservicesApp.Id))" -ForegroundColor Green
Start-Sleep -Seconds 3

# Step 4: Display comparison info
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "BOTH UIs ARE NOW RUNNING!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n🔵 ORIGINAL APP (Monolithic):" -ForegroundColor Cyan
Write-Host "   URL: http://localhost:5002" -ForegroundColor White
Write-Host "   Uses: Direct library imports" -ForegroundColor Gray

Write-Host "`n🟢 MICROSERVICES APP (Distributed):" -ForegroundColor Cyan
Write-Host "   URL: http://localhost:5003" -ForegroundColor White
Write-Host "   Uses: HTTP API calls to microservices" -ForegroundColor Gray

Write-Host "`n📊 COMPARISON TESTING:" -ForegroundColor Yellow
Write-Host "   1. Open both URLs in separate browser tabs" -ForegroundColor White
Write-Host "   2. Submit the same query to both apps" -ForegroundColor White
Write-Host "   3. Compare response times and results" -ForegroundColor White
Write-Host "   4. Verify both produce identical results" -ForegroundColor White

Write-Host "`n🏗️  ARCHITECTURE:" -ForegroundColor Yellow
Write-Host "   Original: Flask → Python libraries" -ForegroundColor White
Write-Host "   Microservices: Flask → HTTP → API Gateway → Services" -ForegroundColor White

Write-Host "`n⚡ PERFORMANCE NOTES:" -ForegroundColor Yellow
Write-Host "   - Original may be faster (no network overhead)" -ForegroundColor Gray
Write-Host "   - Microservices adds ~10-50ms per HTTP call" -ForegroundColor Gray
Write-Host "   - Microservices allows independent scaling" -ForegroundColor Gray

Write-Host "`n⏹️  TO STOP BOTH APPS:" -ForegroundColor Red
Write-Host "   Close the PowerShell windows or press Ctrl+C in each`n" -ForegroundColor White

Write-Host "========================================`n" -ForegroundColor Cyan

# Open browsers
Write-Host "🌐 Opening browsers..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
Start-Process "http://localhost:5002"  # Original
Start-Sleep -Seconds 1
Start-Process "http://localhost:5003"  # Microservices

Write-Host ""
Write-Host "Setup complete! Both UIs are ready for testing." -ForegroundColor Green
Write-Host ""
