# GCS Infrastructure Deployment Script
# Uses Azure Developer CLI (azd) for deployment

param(
    [Parameter(Mandatory = $false)]
    [string]$Location = "northcentralus",
    
    [Parameter(Mandatory = $false)]
    [string]$Environment = "dev"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  GCS Infrastructure Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$subscriptionId = "13267e8e-b8f0-41c3-ba3e-569b3b7c8482"  # From VS Code auth
$resourceGroupName = "rg-gcs-$Environment"
$projectName = "gcs"
$owner = "bprice@microsoft.com"

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Subscription: $subscriptionId"
Write-Host "  Resource Group: $resourceGroupName"
Write-Host "  Location: $Location"
Write-Host "  Environment: $Environment"
Write-Host ""

# Deploy using Bicep
Write-Host "Deploying infrastructure..." -ForegroundColor Green
Write-Host ""

$deploymentName = "gcs-infrastructure-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

try {
    Write-Host "Starting deployment: $deploymentName" -ForegroundColor Cyan
    
    # Deploy at subscription scope
    $deployment = az deployment sub create `
        --name $deploymentName `
        --location $Location `
        --template-file ".\infrastructure\bicep\main.bicep" `
        --parameters location=$Location environment=$Environment projectName=$projectName owner=$owner `
        --subscription $subscriptionId `
        --output json | ConvertFrom-Json
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ Deployment successful!" -ForegroundColor Green
        Write-Host ""
        
        # Display outputs
        Write-Host "Resource Information:" -ForegroundColor Yellow
        Write-Host "  Resource Group: $($deployment.properties.outputs.resourceGroupName.value)"
        Write-Host "  Storage Account: $($deployment.properties.outputs.storageAccountName.value)"
        Write-Host "  App Insights: $($deployment.properties.outputs.appInsightsName.value)"
        Write-Host "  Log Analytics: $($deployment.properties.outputs.logAnalyticsName.value)"
        Write-Host "  Container Registry: $($deployment.properties.outputs.containerRegistryName.value)"
        Write-Host "  Key Vault: $($deployment.properties.outputs.keyVaultName.value)"
        Write-Host ""
        
        # Save outputs to file
        $deployment.properties.outputs | ConvertTo-Json -Depth 10 | Out-File ".\infrastructure\deployment-outputs.json"
        Write-Host "Outputs saved to: .\infrastructure\deployment-outputs.json" -ForegroundColor Cyan
        
    }
    else {
        Write-Host "❌ Deployment failed!" -ForegroundColor Red
        exit 1
    }
    
}
catch {
    Write-Host "❌ Error during deployment:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Phase 1 Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review resources in Azure Portal"
Write-Host "  2. Run: .\infra\scripts\setup-secrets.ps1"
Write-Host "  3. Run: .\infra\scripts\migrate-data.ps1"
Write-Host ""
