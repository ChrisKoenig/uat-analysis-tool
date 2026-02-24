# Azure Key Vault RBAC Permission Setup

> **Last Updated**: February 23, 2026

## When You Need This
Your user account needs permissions to read/write secrets in Key Vault `kv-gcs-dev-gg4a6y`, which is used by the Triage API (port 8009) and Field Portal API (port 8010).

## Solution Options

### Option 1: Azure Portal (Easiest)

1. Open https://portal.azure.com
2. Navigate to the Key Vault: `kv-gcs-dev-gg4a6y`
3. Go to **Access control (IAM)** in the left menu
4. Click **+ Add** → **Add role assignment**
5. Select role: **Key Vault Secrets Officer**
6. Click **Next**
7. Click **+ Select members**
8. Search for your email: `bprice@microsoft.com`
9. Select your account
10. Click **Review + assign**

Wait 2-3 minutes for the role assignment to propagate.

### Option 2: Azure CLI (If available)

```bash
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee bprice@microsoft.com \
  --scope "/subscriptions/13267e8e-b8f0-41c3-ba3e-569b3b7c8482/resourcegroups/rg-gcs-dev/providers/Microsoft.KeyVault/vaults/kv-gcs-dev-gg4a6y"
```

### Option 3: Azure PowerShell (Fresh Session)

Close your current PowerShell terminal and open a new one, then run:

```powershell
Connect-AzAccount
$userId = (Get-AzADUser -UserPrincipalName "bprice@microsoft.com").Id
New-AzRoleAssignment `
  -ObjectId $userId `
  -RoleDefinitionName "Key Vault Secrets Officer" `
  -Scope "/subscriptions/13267e8e-b8f0-41c3-ba3e-569b3b7c8482/resourcegroups/rg-gcs-dev/providers/Microsoft.KeyVault/vaults/kv-gcs-dev-gg4a6y"
```

## What This Role Provides

**Key Vault Secrets Officer** allows you to:
- ✅ Create secrets
- ✅ Read secrets
- ✅ Update secrets
- ✅ Delete secrets
- ✅ List secrets

## After Granting Permissions

1. Wait 2-3 minutes for RBAC propagation
2. Start services:
   - Triage API: `python -m uvicorn triage.api.routes:app --port 8009`
   - Field Portal API: `python -m uvicorn field-portal.api.main:app --port 8010`
3. Both services load secrets from Key Vault at startup via `keyvault_config.py`

## Key Vault Details

- **Name**: kv-gcs-dev-gg4a6y
- **URI**: https://kv-gcs-dev-gg4a6y.vault.azure.net/
- **Resource Group**: rg-gcs-dev
- **Subscription**: 13267e8e-b8f0-41c3-ba3e-569b3b7c8482
- **Location**: North Central US

## Microsoft Security Best Practices

Once secrets are migrated to Key Vault, you should also configure:

### 1. Enable Auditing ✅
- Azure Monitor Diagnostic Settings
- Send logs to Log Analytics workspace
- Monitor secret access patterns

### 2. Network Security
- Configure firewall rules
- Enable private endpoint (optional for higher security)
- Restrict access to specific VNets

### 3. Enable Microsoft Defender for Key Vault
- Real-time threat detection
- Alerts on suspicious access patterns
- Compliance monitoring

### 4. Configure Access Policies
- Use RBAC (recommended) ✅ Already using this
- Principle of least privilege
- Regular access reviews

### 5. Enable Soft Delete & Purge Protection ✅
Should already be enabled on modern Key Vaults

These will be configured in the next steps after secret migration.
