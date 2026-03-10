# Infrastructure — Quick Start Guide

Last Updated: February 23, 2026

## Option 1: Deploy Using Azure Portal (Recommended)

### Step 1: Create Resource Group
1. Open [Azure Portal](https://portal.azure.com)
2. Click **Resource groups** > **+ Create**
3. Fill in:
   - **Subscription:** MCAPS-Hybrid-REQ-53439-2023-bprice
   - **Resource group:** `rg-gcs-dev`
   - **Region:** North Central US
   - **Tags:**
     - Environment: Development
     - Project: Triage Management
     - Owner: bprice@microsoft.com
4. Click **Review + create** > **Create**

### Step 2: Deploy Bicep Template
1. In the resource group, click **Deploy** > **Deploy a custom template**
2. Click **Build your own template in the editor**
3. Click **Load file** and select: `infra/bicep/resources.bicep`
4. Click **Save**
5. Fill in parameters:
   - **Location:** northcentralus
   - **Environment:** dev
   - **ProjectName:** triage
   - **Owner:** bprice@microsoft.com
6. Click **Review + create** > **Create**

⏱️ **Deployment takes ~5-10 minutes**

---

## Option 2: Deploy Using VS Code Azure Extension

### Prerequisites
- Azure Resources extension installed in VS Code (already done ✅)
- Signed in to Azure (already done ✅)

### Steps
1. Open VS Code Command Palette (`Ctrl+Shift+P`)
2. Type: **Azure: Deploy to Azure**
3. Select **Deploy to Resource Group**
4. Choose your subscription: **MCAPS-Hybrid-REQ-53439-2023-bprice**
5. Select **+ Create new resource group**
6. Name it: `rg-gcs-dev`
7. Select region: **North Central US**
8. Select the Bicep file: `infra/bicep/main.bicep`
9. Click **Deploy**

---

## Option 3: Deploy Using PowerShell (If Azure CLI is setup)

### If you want to setup Azure CLI:
1. Open PowerShell as Administrator
2. Run: `az login --use-device-code`
3. Follow the device code flow
4. Then run:
   ```powershell
   .\infra\scripts\deploy-infrastructure.ps1
   ```

---

## What Gets Created

| Resource | Name | Purpose |
|----------|------|---------|
| Resource Group | `rg-gcs-dev` | Container for all resources |
| Cosmos DB Account | `cosmos-gcs-dev` | NoSQL database (triage-management DB) |
| Log Analytics | `log-gcs-dev` | Centralized logging (730-day retention) |
| App Insights | `appi-gcs-dev` | Metrics and monitoring (730-day retention) |
| Key Vault | `kv-gcs-dev-XXXXXX` | Secrets management (Cosmos, OpenAI, storage) |
| Container Registry | `acrgcsdevXXXXXX` | Docker image storage (Standard SKU) |
| Container Apps Env | `cae-gcs-dev` | Container hosting environment |
| Storage Account | `stgcsdevevXXXXXX` | Blob storage (secondary data) |

**Total Cost:** ~$183-417/month

---

## After Deployment

### Verify Resources
1. Go to Azure Portal > Resource groups > `rg-gcs-dev`
2. You should see 7-8 resources created
3. Check deployment status in **Deployments** section

### Get Connection Strings
You'll need these for the next steps:

**Application Insights:**
```powershell
# In Azure Portal: App Insights > Properties
# Copy: Instrumentation Key and Connection String
```

**Storage Account:**
```powershell
# In Azure Portal: Storage Account > Access keys
# Copy: Connection string (key1)
```

**Container Registry:**
```powershell
# In Azure Portal: Container Registry > Access keys
# Enable Admin user
# Copy: Login server, Username, Password
```

### Save to File
Create `.env.azure` file with:
```bash
AZURE_STORAGE_CONNECTION_STRING=<your-connection-string>
AZURE_APP_INSIGHTS_CONNECTION_STRING=<your-connection-string>
AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY=<your-key>
AZURE_CONTAINER_REGISTRY_SERVER=<server>.azurecr.io
AZURE_CONTAINER_REGISTRY_USERNAME=<username>
AZURE_CONTAINER_REGISTRY_PASSWORD=<password>
AZURE_KEY_VAULT_URI=https://<keyvault-name>.vault.azure.net/
```

---

## Next Steps After Infrastructure is Created

1. ✅ Infrastructure deployed
2. ⏭️ Store secrets in Key Vault (see KEYVAULT_MIGRATION_COMPLETE.md)
3. ⏭️ Configure Cosmos DB containers (triage-management database)
4. ⏭️ Deploy Triage API (port 8009) and Field Portal API (port 8010)

---

## Troubleshooting

### "Resource name already exists"
- Add more characters to uniqueSuffix in Bicep
- Or manually create with different names in Portal

### "Quota exceeded"
- Check your subscription quotas
- Request quota increase if needed

### "Permission denied"
- Ensure you have Owner or Contributor role on subscription
- Check with your Azure admin

---

## Need Help?

**Created:** January 17, 2026  
**Last Updated:** February 23, 2026  
**Owner:** bprice@microsoft.com  
**Documentation:** See [DEPLOYMENT_OPERATIONS.md](../docs/DEPLOYMENT_OPERATIONS.md)
