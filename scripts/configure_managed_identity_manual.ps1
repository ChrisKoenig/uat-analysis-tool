# Configure Managed Identity - Manual Steps Guide

Write-Host "=" -Foreground Color Cyan * 80
Write-Host "Managed Identity Configuration Guide" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

Write-Host "Option 1: Use Azure Portal (Easiest)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Step 1: Grant Key Vault Secrets User Role" -ForegroundColor Cyan
Write-Host "  1. Go to: https://portal.azure.com" -ForegroundColor White
Write-Host "  2. Navigate to Key Vault: kv-gcs-dev-gg4a6y" -ForegroundColor White
Write-Host "  3. Click 'Access control (IAM)' in left menu" -ForegroundColor White
Write-Host "  4. Click '+ Add' > 'Add role assignment'" -ForegroundColor White
Write-Host "  5. Select role: 'Key Vault Secrets User'" -ForegroundColor White
Write-Host "  6. Click Next" -ForegroundColor White
Write-Host "  7. Click '+ Select members'" -ForegroundColor White
Write-Host "  8. Search for: mi-gcs-dev" -ForegroundColor White
Write-Host "  9. Select the managed identity" -ForegroundColor White
Write-Host "  10. Click 'Review + assign'" -ForegroundColor White
Write-Host ""

Write-Host "Step 2: Grant Storage Blob Data Contributor Role" -ForegroundColor Cyan
Write-Host "  1. Go to Storage Account: stgcsdevgg4a6y" -ForegroundColor White
Write-Host "  2. Click 'Access control (IAM)' in left menu" -ForegroundColor White
Write-Host "  3. Click '+ Add' > 'Add role assignment'" -ForegroundColor White
Write-Host "  4. Select role: 'Storage Blob Data Contributor'" -ForegroundColor White
Write-Host "  5. Click Next" -ForegroundColor White
Write-Host "  6. Click '+ Select members'" -ForegroundColor White
Write-Host "  7. Search for: mi-gcs-dev" -ForegroundColor White
Write-Host "  8. Select the managed identity" -ForegroundColor White
Write-Host "  9. Click 'Review + assign'" -ForegroundColor White
Write-Host ""

Write-Host "Step 3: Get the Client ID" -ForegroundColor Cyan
Write-Host "  1. Go to: Resource Group > rg-gcs-dev" -ForegroundColor White
Write-Host "  2. Find and click: mi-gcs-dev (Managed Identity)" -ForegroundColor White
Write-Host "  3. Copy the 'Client ID' from the overview page" -ForegroundColor White
Write-Host "  4. Save it for deployment configuration" -ForegroundColor White
Write-Host ""

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "After completing these steps:" -ForegroundColor Yellow
Write-Host "1. Wait 2-3 minutes for permissions to propagate" -ForegroundColor White
Write-Host "2. Test locally (optional): Set environment variable" -ForegroundColor White
Write-Host "   `$env:AZURE_CLIENT_ID = '<client-id-you-copied>'" -ForegroundColor Gray
Write-Host "   python keyvault_config.py" -ForegroundColor Gray
Write-Host "3. For deployment, add AZURE_CLIENT_ID to your app settings" -ForegroundColor White
Write-Host ""
Write-Host "Documentation: MANAGED_IDENTITY_DEPLOYMENT.md" -ForegroundColor Cyan
