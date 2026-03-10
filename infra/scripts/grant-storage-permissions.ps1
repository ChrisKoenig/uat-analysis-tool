# Grant Storage Permissions
# Assigns Storage Blob Data Contributor role to your account

$storageAccountName = "stgcsdevgg4a6y"
$resourceGroup = "rg-gcs-dev"
$userEmail = "bprice@microsoft.com"

Write-Host "🔐 Granting Storage Blob Data Contributor role..." -ForegroundColor Cyan
Write-Host "  Storage Account: $storageAccountName" -ForegroundColor White
Write-Host "  User: $userEmail" -ForegroundColor White
Write-Host ""

# Get user object ID
Write-Host "Looking up user..." -ForegroundColor Yellow
$userId = az ad user show --id $userEmail --query id -o tsv

if ($userId) {
    Write-Host "  ✅ Found user ID: $userId" -ForegroundColor Green
    
    # Get storage account resource ID
    $storageId = az storage account show --name $storageAccountName --resource-group $resourceGroup --query id -o tsv
    
    # Assign role
    Write-Host "Assigning role..." -ForegroundColor Yellow
    az role assignment create `
        --assignee $userId `
        --role "Storage Blob Data Contributor" `
        --scope $storageId
    
    Write-Host ""
    Write-Host "✅ Role assigned successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "⏳ Note: It may take a few minutes for permissions to propagate" -ForegroundColor Yellow
    Write-Host "   Please wait 2-3 minutes before running the migration script again" -ForegroundColor Yellow
} else {
    Write-Host "❌ Could not find user" -ForegroundColor Red
}
