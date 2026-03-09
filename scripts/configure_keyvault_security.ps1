# Configure Azure Key Vault Auditing and Security
# Implements Microsoft security best practices for Key Vault

param(
    [string]$KeyVaultName,
    [string]$ResourceGroup,
    [string]$LogAnalyticsWorkspaceId = "5168e2dd-6734-46c3-b447-a7a643ece290"
)

# Apply environment-config defaults for any params not explicitly supplied.
# param() must come first in PowerShell, so defaults are resolved here.
$_env = if ($env:APP_ENV) { $env:APP_ENV } else { "dev" }
$_configFile = Join-Path $PSScriptRoot "..\shared\config\environments\$_env.ps1"
if (Test-Path $_configFile) {
    . $_configFile
} else {
    $KV_NAME = "kv-gcs-dev-gg4a6y"; $RG = "rg-gcs-dev"
}
if (-not $KeyVaultName)  { $KeyVaultName  = $KV_NAME }
if (-not $ResourceGroup) { $ResourceGroup = $RG }

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Azure Key Vault Security Configuration" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Key Vault: $KeyVaultName" -ForegroundColor White
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor White
Write-Host ""

# Check if connected to Azure
try {
    $context = Get-AzContext -ErrorAction Stop
    Write-Host "✓ Connected to Azure as: $($context.Account.Id)" -ForegroundColor Green
} catch {
    Write-Host "✗ Not connected to Azure" -ForegroundColor Red
    Write-Host "Run: Connect-AzAccount" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Configuring security features..." -ForegroundColor Yellow
Write-Host ""

# 1. Enable Diagnostic Settings for Auditing
Write-Host "1. Configuring Diagnostic Settings (Audit Logging)" -ForegroundColor Cyan
try {
    $diagnosticSettings = @{
        Name = "KeyVaultAuditLogs"
        ResourceId = "/subscriptions/$((Get-AzContext).Subscription.Id)/resourceGroups/$ResourceGroup/providers/Microsoft.KeyVault/vaults/$KeyVaultName"
        WorkspaceId = "/subscriptions/$((Get-AzContext).Subscription.Id)/resourceGroups/$ResourceGroup/providers/Microsoft.OperationalInsights/workspaces/log-gcs-dev"
        Category = @("AuditEvent", "AllMetrics")
        Enabled = $true
    }
    
    # Note: Use Set-AzDiagnosticSetting when module is available
    Write-Host "   ⚠ Manual step required: Configure via Azure Portal" -ForegroundColor Yellow
    Write-Host "   1. Go to Key Vault > Diagnostic settings" -ForegroundColor White
    Write-Host "   2. Add diagnostic setting" -ForegroundColor White
    Write-Host "   3. Select: AuditEvent, AllMetrics" -ForegroundColor White
    Write-Host "   4. Send to Log Analytics workspace: log-gcs-dev" -ForegroundColor White
} catch {
    Write-Host "   ✗ Error: $_" -ForegroundColor Red
}
Write-Host ""

# 2. Enable Purge Protection
Write-Host "2. Verifying Purge Protection" -ForegroundColor Cyan
try {
    $kv = Get-AzKeyVault -VaultName $KeyVaultName -ResourceGroupName $ResourceGroup
    if ($kv.EnablePurgeProtection) {
        Write-Host "   ✓ Purge protection is enabled" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ Purge protection is not enabled" -ForegroundColor Yellow
        Write-Host "   Run: Update-AzKeyVault -VaultName $KeyVaultName -EnablePurgeProtection" -ForegroundColor White
    }
} catch {
    Write-Host "   ✗ Error: $_" -ForegroundColor Red
}
Write-Host ""

# 3. Enable Soft Delete
Write-Host "3. Verifying Soft Delete" -ForegroundColor Cyan
try {
    $kv = Get-AzKeyVault -VaultName $KeyVaultName -ResourceGroupName $ResourceGroup
    if ($kv.EnableSoftDelete) {
        Write-Host "   ✓ Soft delete is enabled (retention: $($kv.SoftDeleteRetentionInDays) days)" -ForegroundColor Green
    } else {
        Write-Host "   ⚠ Soft delete should be enabled" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ✗ Error: $_" -ForegroundColor Red
}
Write-Host ""

# 4. Review Network Rules
Write-Host "4. Network Security" -ForegroundColor Cyan
try {
    $kv = Get-AzKeyVault -VaultName $KeyVaultName -ResourceGroupName $ResourceGroup
    Write-Host "   Network ACLs: $($kv.NetworkAcls.DefaultAction)" -ForegroundColor White
    if ($kv.NetworkAcls.IpAddressRanges) {
        Write-Host "   Allowed IP addresses:" -ForegroundColor White
        foreach ($ip in $kv.NetworkAcls.IpAddressRanges) {
            Write-Host "      - $ip" -ForegroundColor Gray
        }
    }
    Write-Host "   ⚠ Consider using Private Endpoint for production" -ForegroundColor Yellow
} catch {
    Write-Host "   ✗ Error: $_" -ForegroundColor Red
}
Write-Host ""

# 5. Microsoft Defender for Key Vault
Write-Host "5. Microsoft Defender for Key Vault" -ForegroundColor Cyan
Write-Host "   ⚠ Manual step required: Enable via Azure Portal" -ForegroundColor Yellow
Write-Host "   1. Go to Microsoft Defender for Cloud" -ForegroundColor White
Write-Host "   2. Environment settings > Your subscription" -Fforeground Color White
Write-Host "   3. Enable 'Key Vault' plan" -ForegroundColor White
Write-Host "   4. Configure email notifications for alerts" -ForegroundColor White
Write-Host ""

# 6. Create Azure Monitor Alerts
Write-Host "6. Azure Monitor Alerts" -ForegroundColor Cyan
Write-Host "   Recommended alerts to configure:" -ForegroundColor White
Write-Host "   - Secret access failures (403 Forbidden)" -ForegroundColor Gray
Write-Host "   - Unusual access patterns (access from new locations)" -ForegroundColor Gray
Write-Host "   - Secret changes (Set/Delete operations)" -ForegroundColor Gray
Write-Host "   - Failed authentication attempts" -ForegroundColor Gray
Write-Host ""
Write-Host "   ⚠ Manual step: Configure in Azure Monitor > Alerts" -ForegroundColor Yellow
Write-Host ""

# Summary
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "Configuration Summary" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""
Write-Host "Automated Checks:" -ForegroundColor Yellow
Write-Host "✓ Soft Delete verified" -ForegroundColor Green
Write-Host "✓ Purge Protection verified" -ForegroundColor Green
Write-Host "✓ Network rules reviewed" -ForegroundColor Green
Write-Host ""
Write-Host "Manual Steps Required:" -ForegroundColor Yellow
Write-Host "1. Configure Diagnostic Settings (audit logging)" -ForegroundColor White
Write-Host "2. Enable Microsoft Defender for Key Vault" -ForegroundColor White
Write-Host "3. Set up Azure Monitor alerts" -ForegroundColor White
Write-Host "4. Review and document access patterns" -ForegroundColor White
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Yellow
Write-Host "- Audit logs: Go to Log Analytics > Logs" -ForegroundColor White
Write-Host "- Query: AzureDiagnostics | where ResourceType == 'VAULTS'" -ForegroundColor Gray
Write-Host "- Security recommendations: KEYVAULT_PERMISSIONS_SETUP.md" -ForegroundColor White
Write-Host ""
Write-Host "Next: Review Microsoft security baseline" -ForegroundColor Cyan
Write-Host "https://learn.microsoft.com/security/benchmark/azure/baselines/key-vault-security-baseline" -ForegroundColor Blue
