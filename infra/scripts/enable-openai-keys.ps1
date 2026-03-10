# Enable API Key Authentication for Azure OpenAI
# This sets disableLocalAuth to false

$resourceName = "OpenAI-bp-NorthCentral"
$resourceGroup = "bpAI-NorthCentral"  # You may need to verify this resource group name
$subscriptionId = "13267e8e-b8f0-41c3-ba3e-569b3b7c8482"

Write-Host "Enabling API key authentication for $resourceName..." -ForegroundColor Yellow

# Using Azure REST API via az command
az rest --method patch `
    --uri "https://management.azure.com/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.CognitiveServices/accounts/$resourceName?api-version=2023-05-01" `
    --body '{\"properties\": {\"disableLocalAuth\": false}}'

Write-Host "✅ API key authentication enabled!" -ForegroundColor Green
Write-Host "Now click 'Show Keys' button in Azure Portal to see your keys." -ForegroundColor Cyan
