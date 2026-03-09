# Grant Managed Identity Access to Key Vault
# Run this in a NEW PowerShell window

Write-Host "Configuring Managed Identity for Key Vault Access" -ForegroundColor Cyan
Write-Host ""

# Connect to Azure
try {
    $context = Get-AzContext -ErrorAction Stop
    Write-Host "Connected to Azure as: $($context.Account.Id)" -ForegroundColor Green
}
catch {
    Write-Host "Connecting to Azure..." -ForegroundColor Yellow
    Connect-AzAccount
}

# Get the managed identity
Write-Host ""
Write-Host "Getting managed identity details..." -ForegroundColor Cyan
$mi = Get-AzUserAssignedIdentity -Name "mi-gcs-dev" -ResourceGroupName "rg-gcs-dev"
Write-Host "Managed Identity: $($mi.Name)" -ForegroundColor Green
Write-Host "  Client ID: $($mi.ClientId)" -ForegroundColor Gray
Write-Host "  Principal ID: $($mi.PrincipalId)" -ForegroundColor Gray

# Grant Key Vault Secrets User role
Write-Host ""
Write-Host "Granting Key Vault Secrets User role..." -ForegroundColor Cyan
try {
    $scope = "/subscriptions/13267e8e-b8f0-41c3-ba3e-569b3b7c8482/resourcegroups/rg-gcs-dev/providers/Microsoft.KeyVault/vaults/kv-gcs-dev-gg4a6y"
    
    New-AzRoleAssignment -ObjectId $mi.PrincipalId -RoleDefinitionName "Key Vault Secrets User" -Scope $scope -ErrorAction Stop
    
    Write-Host "Successfully granted Key Vault Secrets User role" -ForegroundColor Green
}
catch {
    if ($_.Exception.Message -like "*already exists*") {
        Write-Host "Role assignment already exists" -ForegroundColor Green
    }
    else {
        Write-Host "Error: $_" -ForegroundColor Red
        exit 1
    }
}

# Grant Storage Blob Data Contributor for Managed Identity-based storage access
Write-Host ""
Write-Host "Granting Storage Blob Data Contributor role..." -ForegroundColor Cyan
try {
    $storageScope = "/subscriptions/13267e8e-b8f0-41c3-ba3e-569b3b7c8482/resourcegroups/rg-gcs-dev/providers/Microsoft.Storage/storageAccounts/stgcsdevgg4a6y"
    
    New-AzRoleAssignment -ObjectId $mi.PrincipalId -RoleDefinitionName "Storage Blob Data Contributor" -Scope $storageScope -ErrorAction Stop
    
    Write-Host "Successfully granted Storage Blob Data Contributor role" -ForegroundColor Green
}
catch {
    if ($_.Exception.Message -like "*already exists*") {
        Write-Host "Role assignment already exists" -ForegroundColor Green
    }
    else {
        Write-Host "Error: $_" -ForegroundColor Red
    }
}

# Summary
Write-Host ""
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host "Configuration Complete" -ForegroundColor Cyan
Write-Host ("=" * 80) -ForegroundColor Cyan
Write-Host ""
Write-Host "Managed Identity: mi-gcs-dev" -ForegroundColor White
Write-Host "Client ID: $($mi.ClientId)" -ForegroundColor Gray
Write-Host "Principal ID: $($mi.PrincipalId)" -ForegroundColor Gray
Write-Host ""
Write-Host "Permissions Granted:" -ForegroundColor Yellow
Write-Host "Key Vault Secrets User (read secrets)" -ForegroundColor Green
Write-Host "Storage Blob Data Contributor (read/write blobs)" -ForegroundColor Green
Write-Host "Contributor (resource group - already configured)" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Add to .env.azure: AZURE_CLIENT_ID=$($mi.ClientId)" -ForegroundColor White
Write-Host "2. Application will use managed identity when deployed" -ForegroundColor White
Write-Host "3. For local dev, continues using your user credentials" -ForegroundColor White
