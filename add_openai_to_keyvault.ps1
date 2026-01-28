# Add Azure OpenAI Configuration to Key Vault
# Run this script to populate the Azure OpenAI secrets in Key Vault

Write-Host "`n=== Adding Azure OpenAI Configuration to Key Vault ===" -ForegroundColor Cyan

# Azure OpenAI Configuration from infrastructure\GET_CONNECTION_STRINGS.md
$AZURE_OPENAI_ENDPOINT = "https://OpenAI-bp-NorthCentral.openai.azure.com/"
$AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT = "gpt-4o-02"
$AZURE_OPENAI_EMBEDDING_DEPLOYMENT = "text-embedding-3-large"

Write-Host "`nNote: Using Azure AD authentication (API key not required)" -ForegroundColor Yellow
Write-Host "AZURE_OPENAI_USE_AAD is already set to 'true' in Key Vault`n" -ForegroundColor Gray

Write-Host "`nAdding secrets to Key Vault..." -ForegroundColor Yellow

# Get Key Vault name
$kvName = "kv-gcs-dev-gg4a6y"

# Add secrets using Azure CLI
Write-Host "   1. AZURE_OPENAI_ENDPOINT..." -ForegroundColor Gray
az keyvault secret set --vault-name $kvName --name "AZURE-OPENAI-ENDPOINT" --value $AZURE_OPENAI_ENDPOINT --output none
if ($LASTEXITCODE -eq 0) { Write-Host "      ✅ Set" -ForegroundColor Green } else { Write-Host "      ❌ Failed" -ForegroundColor Red }

Write-Host "   2. AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT..." -ForegroundColor Gray
az keyvault secret set --vault-name $kvName --name "AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT" --value $AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT --output none
if ($LASTEXITCODE -eq 0) { Write-Host "      ✅ Set" -ForegroundColor Green } else { Write-Host "      ❌ Failed" -ForegroundColor Red }

Write-Host "   3. AZURE_OPENAI_EMBEDDING_DEPLOYMENT..." -ForegroundColor Gray
az keyvault secret set --vault-name $kvName --name "AZURE-OPENAI-EMBEDDING-DEPLOYMENT" --value $AZURE_OPENAI_EMBEDDING_DEPLOYMENT --output none
if ($LASTEXITCODE -eq 0) { Write-Host "      ✅ Set" -ForegroundColor Green } else { Write-Host "      ❌ Failed" -ForegroundColor Red }

Write-Host "`n=== Configuration Complete ===" -ForegroundColor Green
Write-Host "Azure OpenAI settings have been added to Key Vault." -ForegroundColor Green
Write-Host "Using Azure AD authentication (no API key needed)." -ForegroundColor Cyan
Write-Host "Run .\start_app.ps1 to start the application with AI enabled." -ForegroundColor Cyan
