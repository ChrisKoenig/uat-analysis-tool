# Managed Identity Deployment Guide

## Overview
Your application now supports **both local development and production deployment** with managed identity `mi-gcs-dev`.

## Architecture

### Local Development (Current)
```
Your Machine
  └─ DefaultAzureCredential
      ├─ Azure CLI / PowerShell (authenticated)
      └─ VS Code (if available)
         ↓
    Key Vault (kv-gcs-dev-gg4a6y)
         ↓
    Triage API (port 8009) + Field Portal API (port 8010)
         ↓
    Cosmos DB (triage-management) + Azure OpenAI
```

### Production Deployment (Configured)
```
Azure Container App / App Service
  └─ User-Assigned Identity: mi-gcs-dev
         ↓
    Key Vault (kv-gcs-dev-gg4a6y)
         ↓
    Triage API + Field Portal API
         ↓
    Cosmos DB + Azure OpenAI
```

## Setup Instructions

### Step 1: Configure Managed Identity Permissions
Run this in a **new PowerShell window**:

```powershell
.\scripts\configure_managed_identity.ps1
```

This script will:
- ✅ Get the managed identity details
- ✅ Grant Key Vault Secrets User role
- ✅ Grant Storage Blob Data Contributor role
- ✅ Display the Client ID for deployment configuration

### Step 2: Get Managed Identity Client ID
After running the script above, note the **Client ID** displayed. You'll need it for deployment.

**Or get it manually:**
```powershell
$mi = Get-AzUserAssignedIdentity -Name "mi-gcs-dev" -ResourceGroupName "rg-gcs-dev"
Write-Host "Client ID: $($mi.ClientId)"
```

### Step 3: Configure for Production Deployment

**For Azure Container Apps:**
```bash
# Assign the managed identity to your container app
az containerapp identity assign \
  --name <your-app-name> \
  --resource-group rg-gcs-dev \
  --user-assigned /subscriptions/13267e8e-b8f0-41c3-ba3e-569b3b7c8482/resourcegroups/rg-gcs-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/mi-gcs-dev

# Set environment variable
az containerapp update \
  --name <your-app-name> \
  --resource-group rg-gcs-dev \
  --set-env-vars "AZURE_CLIENT_ID=<client-id-from-step-2>"
```

**For Azure App Service:**
```bash
# Assign the managed identity
az webapp identity assign \
  --name <your-app-name> \
  --resource-group rg-gcs-dev \
  --identities /subscriptions/13267e8e-b8f0-41c3-ba3e-569b3b7c8482/resourcegroups/rg-gcs-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/mi-gcs-dev

# Set environment variable
az webapp config appsettings set \
  --name <your-app-name> \
  --resource-group rg-gcs-dev \
  --settings AZURE_CLIENT_ID=<client-id-from-step-2>
```

## How It Works

### Code Behavior

**keyvault_config.py** (`shared/keyvault_config.py`):
```python
# Checks for AZURE_CLIENT_ID environment variable
if managed_identity_client_id:
    # Production: Use managed identity
    credential = ManagedIdentityCredential(client_id=managed_identity_client_id)
else:
    # Development: Use your user credentials
    credential = DefaultAzureCredential()
```

**blob_storage_helper.py** (`shared/blob_storage_helper.py`):
```python
# Checks for AZURE_CLIENT_ID environment variable
if managed_identity_client_id:
    # Production: Use managed identity for storage
    credential = ManagedIdentityCredential(client_id=managed_identity_client_id)
    blob_client = BlobServiceClient(account_url=url, credential=credential)
else:
    # Development: Use connection string from Key Vault
    blob_client = BlobServiceClient.from_connection_string(connection_string)
```

### Development vs Production

| Aspect | Development (Local) | Production (Azure) |
|--------|---------------------|-------------------|
| **Key Vault Auth** | DefaultAzureCredential | ManagedIdentityCredential |
| **Storage Auth** | Connection String | Managed Identity |
| **Config Required** | None (uses your login) | AZURE_CLIENT_ID env var |
| **Secrets** | From Key Vault + .env | From Key Vault only |

## Testing

### Test Locally (Development Mode)
```powershell
# Should show: Authentication: DefaultAzureCredential
python shared/keyvault_config.py
```

### Test with Managed Identity (Simulated)
```powershell
# Set the environment variable temporarily
$env:AZURE_CLIENT_ID = "<client-id-from-step-2>"

# Run test - should show: Authentication: Managed Identity
python shared/keyvault_config.py

# Unset when done
Remove-Item Env:AZURE_CLIENT_ID
```

## Permissions Summary

The managed identity `mi-gcs-dev` has been granted:

| Resource | Role | Purpose |
|----------|------|---------|
| **Resource Group** (rg-gcs-dev) | Contributor | Manage all resources in group |
| **Key Vault** (kv-gcs-dev-gg4a6y) | Key Vault Secrets User | Read secrets |
| **Storage Account** (stgcsdevgg4a6y) | Storage Blob Data Contributor | Read/write blobs |

## Security Benefits

### ✅ No Secrets in Code or Config
- Application code contains NO connection strings
- Application code contains NO API keys
- Deployment configuration contains NO secrets

### ✅ Automatic Credential Rotation
- Managed identity tokens auto-rotate (no manual rotation needed)
- No expired credentials to worry about

### ✅ Audit Trail
- All Key Vault access logged with managed identity as caller
- All storage access logged with managed identity as caller
- Full compliance and security tracking

### ✅ Principle of Least Privilege
- Managed identity has only required permissions
- Scoped to specific resources (not subscription-wide)
- Can be reviewed and audited easily

## Deployment Checklist

- [ ] Run `.\configure_managed_identity.ps1` in new PowerShell window
- [ ] Note the Client ID from the output
- [ ] Assign managed identity to Container App / App Service
- [ ] Set `AZURE_CLIENT_ID` environment variable in deployment
- [ ] Copy non-secret config from `.env.azure.clean` to app settings
- [ ] Test the deployed application
- [ ] Verify audit logs in Log Analytics
- [ ] Document the deployment for runbook

## Troubleshooting

### Issue: "ManagedIdentityCredential authentication unavailable"
**Solution:** Ensure `AZURE_CLIENT_ID` is set in the environment and the managed identity is assigned to the app.

### Issue: "Caller is not authorized"
**Solution:** Run `.\configure_managed_identity.ps1` again to verify permissions are granted.

### Issue: Works locally but fails in Azure
**Solution:** 
1. Check that managed identity is assigned to the app
2. Verify AZURE_CLIENT_ID environment variable is set
3. Check that managed identity has the required RBAC roles

## Next Steps

1. **Complete Key Vault Auditing Configuration**
   - Run `.\configure_keyvault_security.ps1` for guidance
   - Enable diagnostic logging in Azure Portal

2. **Deploy to Azure Container Apps**
   - Build container image
   - Push to ACR (acrgcsdevgg4a6y)
   - Deploy with managed identity configuration

3. **Monitor and Alert**
   - Set up Application Insights alerts
   - Configure Key Vault access alerts
   - Review audit logs regularly

## Documentation

- [KEYVAULT_MIGRATION_COMPLETE.md](KEYVAULT_MIGRATION_COMPLETE.md) — Key Vault integration details
- [KEYVAULT_PERMISSIONS_SETUP.md](KEYVAULT_PERMISSIONS_SETUP.md) — RBAC permission setup
- [AZURE_OPENAI_AUTH_SETUP.md](AZURE_OPENAI_AUTH_SETUP.md) — OpenAI resource config

---

**Last Updated**: February 23, 2026
