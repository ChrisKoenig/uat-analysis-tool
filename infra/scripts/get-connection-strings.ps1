# Get GCS Infrastructure Connection Strings
# Run this script to collect all connection strings and keys needed

param(
    [string]$ResourceGroup = "rg-gcs-dev",
    [string]$OutputFile = ".env.azure"
)

Write-Host "🔍 Retrieving connection strings from resource group: $ResourceGroup" -ForegroundColor Cyan
Write-Host ""

# Initialize output
$envContent = @"
# GCS Azure Infrastructure Connection Strings
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Resource Group: $ResourceGroup

"@

# Get Storage Account Connection String
Write-Host "📦 Storage Account..." -ForegroundColor Yellow
$storageAccount = az storage account list --resource-group $ResourceGroup --query "[?starts_with(name, 'stgcsdev')].name" -o tsv
if ($storageAccount) {
    $storageConnectionString = az storage account show-connection-string --name $storageAccount --resource-group $ResourceGroup --query "connectionString" -o tsv
    $envContent += "AZURE_STORAGE_ACCOUNT_NAME=$storageAccount`n"
    $envContent += "AZURE_STORAGE_CONNECTION_STRING=$storageConnectionString`n"
    Write-Host "  ✅ Storage: $storageAccount" -ForegroundColor Green
}

# Get Application Insights Connection String
Write-Host "📊 Application Insights..." -ForegroundColor Yellow
$appInsightsName = "appi-gcs-dev"
$appInsightsKey = az monitor app-insights component show --app $appInsightsName --resource-group $ResourceGroup --query "instrumentationKey" -o tsv 2>$null
$appInsightsConnectionString = az monitor app-insights component show --app $appInsightsName --resource-group $ResourceGroup --query "connectionString" -o tsv 2>$null

if ($appInsightsKey) {
    $envContent += "`nAZURE_APP_INSIGHTS_INSTRUMENTATION_KEY=$appInsightsKey`n"
    $envContent += "AZURE_APP_INSIGHTS_CONNECTION_STRING=$appInsightsConnectionString`n"
    Write-Host "  ✅ Application Insights: $appInsightsName" -ForegroundColor Green
}

# Get Container Registry Credentials
Write-Host "🐳 Container Registry..." -ForegroundColor Yellow
$acrName = az acr list --resource-group $ResourceGroup --query "[?starts_with(name, 'acrgcsdev')].name" -o tsv
if ($acrName) {
    # Enable admin user
    az acr update --name $acrName --admin-enabled true | Out-Null
    
    $acrServer = az acr show --name $acrName --resource-group $ResourceGroup --query "loginServer" -o tsv
    $acrUsername = az acr credential show --name $acrName --query "username" -o tsv
    $acrPassword = az acr credential show --name $acrName --query "passwords[0].value" -o tsv
    
    $envContent += "`nAZURE_CONTAINER_REGISTRY_NAME=$acrName`n"
    $envContent += "AZURE_CONTAINER_REGISTRY_SERVER=$acrServer`n"
    $envContent += "AZURE_CONTAINER_REGISTRY_USERNAME=$acrUsername`n"
    $envContent += "AZURE_CONTAINER_REGISTRY_PASSWORD=$acrPassword`n"
    Write-Host "  ✅ Container Registry: $acrName" -ForegroundColor Green
}

# Get Key Vault URI
Write-Host "🔐 Key Vault..." -ForegroundColor Yellow
$keyVaultName = az keyvault list --resource-group $ResourceGroup --query "[?starts_with(name, 'kv-gcs-dev')].name" -o tsv
if ($keyVaultName) {
    $keyVaultUri = az keyvault show --name $keyVaultName --resource-group $ResourceGroup --query "properties.vaultUri" -o tsv
    $envContent += "`nAZURE_KEY_VAULT_NAME=$keyVaultName`n"
    $envContent += "AZURE_KEY_VAULT_URI=$keyVaultUri`n"
    Write-Host "  ✅ Key Vault: $keyVaultName" -ForegroundColor Green
}

# Get Log Analytics Workspace ID
Write-Host "📝 Log Analytics..." -ForegroundColor Yellow
$logWorkspaceName = "log-gcs-dev"
$logWorkspaceId = az monitor log-analytics workspace show --resource-group $ResourceGroup --workspace-name $logWorkspaceName --query "customerId" -o tsv 2>$null
if ($logWorkspaceId) {
    $envContent += "`nAZURE_LOG_ANALYTICS_WORKSPACE_ID=$logWorkspaceId`n"
    Write-Host "  ✅ Log Analytics: $logWorkspaceName" -ForegroundColor Green
}

# Get Container Apps Environment
Write-Host "📦 Container Apps Environment..." -ForegroundColor Yellow
$caeName = "cae-gcs-dev"
$caeId = az containerapp env show --name $caeName --resource-group $ResourceGroup --query "id" -o tsv 2>$null
if ($caeId) {
    $envContent += "`nAZURE_CONTAINER_APPS_ENVIRONMENT=$caeName`n"
    $envContent += "AZURE_CONTAINER_APPS_ENVIRONMENT_ID=$caeId`n"
    Write-Host "  ✅ Container Apps Environment: $caeName" -ForegroundColor Green
}

# Add existing OpenAI resource
Write-Host "🤖 Azure OpenAI (existing)..." -ForegroundColor Yellow
$envContent += "`n# Existing Azure OpenAI Resource`n"
$envContent += "AZURE_OPENAI_RESOURCE_NAME=OpenAI-bp-NorthCentral`n"
$envContent += "AZURE_OPENAI_ENDPOINT=https://OpenAI-bp-NorthCentral.openai.azure.com/`n"
$envContent += "# Get the key from Azure Portal: OpenAI-bp-NorthCentral > Keys and Endpoint`n"
$envContent += "AZURE_OPENAI_API_KEY=<your-openai-key-here>`n"
Write-Host "  ⚠️  Please manually add OpenAI key from Azure Portal" -ForegroundColor Yellow

# Write to file
$envContent | Out-File -FilePath $OutputFile -Encoding UTF8

Write-Host ""
Write-Host "✅ Connection strings saved to: $OutputFile" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  IMPORTANT:" -ForegroundColor Yellow
Write-Host "  1. Review the $OutputFile file" -ForegroundColor White
Write-Host "  2. Add your Azure OpenAI API key manually" -ForegroundColor White
Write-Host "  3. DO NOT commit this file to git (it's in .gitignore)" -ForegroundColor White
Write-Host ""
Write-Host "📋 Resource Group: $ResourceGroup" -ForegroundColor Cyan
Write-Host "🌐 Azure Portal: https://portal.azure.com/#@microsoft.onmicrosoft.com/resource/subscriptions/13267e8e-b8f0-41c3-ba3e-569b3b7c8482/resourceGroups/$ResourceGroup/overview" -ForegroundColor Cyan
