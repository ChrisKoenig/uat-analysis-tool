# Startup script for Flask app with Azure OpenAI integration + Microservices
# Last updated: January 23, 2026
# Starts: API Gateway (8000) + Microservices (8001-8007) + Admin Portal (8008) + Flask App (5003)

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Issue Tracker System - Full Stack Startup" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# Set managed identity for production deployment (comment out for local dev)
Write-Host "`n[1/7] Setting up authentication..." -ForegroundColor Yellow
# Uncomment next line ONLY when deploying to Azure:
# $env:AZURE_CLIENT_ID = "7846e03e-9279-4057-bdcd-4a2f7f8ebe85"
Write-Host "   Using local Azure CLI authentication" -ForegroundColor Gray

# Set Azure OpenAI environment variables (East endpoint)
Write-Host "`n[2/7] Loading configuration from Azure Key Vault..." -ForegroundColor Yellow

# Load from Key Vault via keyvault_config.py
Write-Host "   Loading secrets from Azure Key Vault..." -ForegroundColor Gray
$kvConfig = python -c "from keyvault_config import get_keyvault_config; kv = get_keyvault_config(); cfg = kv.get_config(); print((cfg.get('AZURE_OPENAI_ENDPOINT') or '') + '|' + (cfg.get('AZURE_OPENAI_API_KEY') or '') + '|' + (cfg.get('AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT') or '') + '|' + (cfg.get('AZURE_OPENAI_EMBEDDING_DEPLOYMENT') or ''))"
$parts = $kvConfig -split '\|'
$env:AZURE_OPENAI_ENDPOINT = $parts[0]
$env:AZURE_OPENAI_API_KEY = $parts[1]
$env:AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT = $parts[2]
$env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT = $parts[3]

Write-Host "   Endpoint: $env:AZURE_OPENAI_ENDPOINT" -ForegroundColor Gray
Write-Host "   Classification Model: $env:AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT" -ForegroundColor Gray
Write-Host "   Embedding Model: $env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT" -ForegroundColor Gray

# Clean up existing Python processes (ensure clean slate)
Write-Host "`n[3/7] Cleaning up any existing Python services..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "   ✅ Cleanup complete" -ForegroundColor Green

# Verify Python is available
Write-Host "`n[4/7] Verifying Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "   $pythonVersion" -ForegroundColor Gray
} catch {
    Write-Host "   ERROR: Python not found! Please install Python 3.10 or higher." -ForegroundColor Red
    Write-Host "`n`nPress any key to exit..." -ForegroundColor Red
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# Start API Gateway
Write-Host "`n[5/7] Starting API Gateway (port 8000)..." -ForegroundColor Yellow
Start-Process python -ArgumentList "api_gateway.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot"
Start-Sleep -Seconds 3

# Start Microservices
Write-Host "`n[6/7] Starting 7 Microservices..." -ForegroundColor Yellow
Write-Host "   - Context Analyzer (8001)" -ForegroundColor Gray
Start-Process python -ArgumentList "service.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot\agents\context-analyzer"
Start-Sleep -Seconds 2

Write-Host "   - Search Service (8002)" -ForegroundColor Gray
Start-Process python -ArgumentList "service.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot\agents\search-service"
Start-Sleep -Seconds 2

Write-Host "   - Enhanced Matching (8003)" -ForegroundColor Gray
Start-Process python -ArgumentList "service.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot\agents\enhanced-matching"
Start-Sleep -Seconds 2

Write-Host "   - UAT Management (8004)" -ForegroundColor Gray
Start-Process python -ArgumentList "service.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot\agents\uat-management"
Start-Sleep -Seconds 2

Write-Host "   - LLM Classifier (8005)" -ForegroundColor Gray
Start-Process python -ArgumentList "service.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot\agents\llm-classifier"
Start-Sleep -Seconds 2

Write-Host "   - Embedding Service (8006)" -ForegroundColor Gray
Start-Process python -ArgumentList "service.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot\agents\embedding-service"
Start-Sleep -Seconds 2

Write-Host "   - Vector Search (8007)" -ForegroundColor Gray
Start-Process python -ArgumentList "service.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot\agents\vector-search"
Start-Sleep -Seconds 2

Write-Host "   - Admin Portal (8008)" -ForegroundColor Gray
Start-Process python -ArgumentList "admin_service.py" -NoNewWindow -WorkingDirectory "$PSScriptRoot"
Start-Sleep -Seconds 2

Write-Host "`n   All 7 microservices + Admin Portal started!" -ForegroundColor Green

# Start Flask application
Write-Host "`n[7/7] Starting Flask application (port 5003) and Teams Bot (port 3978)..." -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 Web UI: http://localhost:5003" -ForegroundColor Green
Write-Host "🤖 Teams Bot: http://localhost:3978/api/messages" -ForegroundColor Green
Write-Host "🔌 API Gateway: http://localhost:8000" -ForegroundColor Green
Write-Host "📊 Context Analyzer: http://localhost:8001" -ForegroundColor Cyan
Write-Host "🔍 Search Service: http://localhost:8002" -ForegroundColor Cyan
Write-Host "🎯 Enhanced Matching: http://localhost:8003" -ForegroundColor Cyan
Write-Host "📋 UAT Management: http://localhost:8004" -ForegroundColor Cyan
Write-Host "🤖 LLM Classifier: http://localhost:8005" -ForegroundColor Cyan
Write-Host "🔢 Embedding Service: http://localhost:8006" -ForegroundColor Cyan
Write-Host "🔎 Vector Search: http://localhost:8007" -ForegroundColor Cyan
Write-Host "⚙️  Admin Portal: http://localhost:8008" -ForegroundColor Magenta
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Start Teams Bot in background
Write-Host "Starting Teams Bot..." -ForegroundColor Gray
Start-Process python -ArgumentList "bot.py" -NoNewWindow -WorkingDirectory "C:\Projects\Hack-TeamsBot"
Start-Sleep -Seconds 3

# Start Flask app in foreground (blocking)
python app.py

Write-Host "`n`nApplication stopped. Cleaning up microservices..." -ForegroundColor Red
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "Press any key to exit..." -ForegroundColor Red
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
