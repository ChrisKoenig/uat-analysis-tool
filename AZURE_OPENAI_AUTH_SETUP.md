# Azure OpenAI Authentication Setup Guide

> **Last Updated**: February 23, 2026

Reference document for Azure OpenAI resource configuration, authentication, and role assignments used by the Triage and Field Portal systems.

---

## Correct Configuration

### Azure OpenAI Resource
- **Name**: OpenAI-bp-NorthCentral
- **Location**: North Central US
- **Subscription**: MCAPS-Hybrid-REQ-53439-2023-bprice (ID: 13267e8e-b8f0-41c3-ba3e-509b3c7c8482)
- **Tenant**: Microsoft Non-Production (fdpo.onmicrosoft.com)
- **Tenant ID**: `16b3c013-d300-468d-ac64-7eda0820b6d3`
- **Endpoint**: https://OpenAI-bp-NorthCentral.openai.azure.com/

### Deployments
- **Classification**: `gpt-4o-standard` (Standard tier, GPT-4o model)
- **Embeddings**: `text-embedding-3-large` (3072 dimensions)

### Authentication
- **Method**: Azure AD (Entra ID) authentication - **API keys disabled by policy**
- **Local Development**: InteractiveBrowserCredential with tenant ID
- **Azure Deployment**: Managed Identity `mi-gcs-dev` (Client ID: 7846e03e-9279-4057-bdcd-4a2f7f8ebe85)

### Key Vault Configuration
All secrets stored in: **kv-gcs-dev-gg4a6y.vault.azure.net**

Required secrets:
```
AZURE-OPENAI-ENDPOINT = https://OpenAI-bp-NorthCentral.openai.azure.com/
AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT = gpt-4o-standard
AZURE-OPENAI-EMBEDDING-DEPLOYMENT = text-embedding-3-large
AZURE-OPENAI-USE-AAD = true
```

**Note**: `AZURE-OPENAI-API-KEY` secret does NOT exist (and should not) - using Azure AD only.

---

## Required Role Assignments

### For Local Development (User Account)
**Principal**: Brad.Price@microsoft.com (Object ID: f1a846d2-dca1-4402-b526-e5b3e5643bb7)

**Roles needed**:
1. **Cognitive Services OpenAI User** on OpenAI-bp-NorthCentral resource
   - Scope: Resource level
   - Purpose: API access for chat completions, embeddings
   
2. **Key Vault Secrets User** (or higher) on kv-gcs-dev-gg4a6y
   - Scope: Key Vault level
   - Purpose: Read secrets for configuration

### For Azure Deployment (Managed Identity)
**Principal**: mi-gcs-dev (Client ID: 7846e03e-9279-4057-bdcd-4a2f7f8ebe85)

**Roles needed**:
1. **Cognitive Services OpenAI User** on OpenAI-bp-NorthCentral resource
2. **Key Vault Secrets User** on kv-gcs-dev-gg4a6y
3. **Storage Blob Data Contributor** on stgcsdevgg4a6y

---

## Services Using Azure OpenAI

| Service | Port | Usage |
|---------|------|-------|
| Triage API | 8009 | Evaluation pipeline AI analysis |
| Field Portal API | 8010 | Quality evaluation, context analysis |

---

## Configuration Priority

**CRITICAL**: Configuration loading order:
1. **Key Vault** (primary source) ✅
2. **Environment variables** (fallback only)
3. **`.env` file** (REMOVED - was causing conflicts)

The `.env` file has been renamed to `.env.backup` to prevent it from overriding Key Vault configuration.

---

## Common Issues & Solutions

### Issue: "Token tenant does not match resource tenant"
**Cause**: Authenticating to wrong tenant (corporate 72f988bf... instead of Non-Production 16b3c013...)

**Solution**:
- Ensure `InteractiveBrowserCredential` specifies `tenant_id="16b3c013-d300-468d-ac64-7eda0820b6d3"`
- DO NOT use `DefaultAzureCredential()` without tenant specification
- Verify token tenant: `python check_token_tenant.py`

### Issue: "PermissionDenied" or 401 errors
**Cause**: User account missing required role assignment

**Solution**:
1. Go to OpenAI-bp-NorthCentral → Access control (IAM)
2. Add role assignment: Cognitive Services OpenAI User
3. Assign to: Brad.Price@microsoft.com
4. Wait 1-2 minutes for propagation

### Issue: "DeploymentNotFound" errors
**Cause**: Wrong deployment name in Key Vault

**Solution**:
- Verify deployment name in Azure Portal: OpenAI-bp-NorthCentral → Model deployments
- Update Key Vault secret: `AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT = gpt-4o-standard`
- Restart services to reload configuration

### Issue: Pattern matching fallback warning
**Cause**: AI service unable to authenticate or connect

**Solution**:
1. Check Key Vault has correct endpoint and deployment
2. Verify role assignments are in place
3. Confirm services loaded Key Vault config (not .env)
4. Check debug logs for initialization messages
5. Run diagnostic: `python test_ai_integration.py`

---

## Related Documentation
- [KEYVAULT_MIGRATION_COMPLETE.md](KEYVAULT_MIGRATION_COMPLETE.md) — Key Vault secret setup
- [MANAGED_IDENTITY_DEPLOYMENT.md](MANAGED_IDENTITY_DEPLOYMENT.md) — Managed identity deployment
- [KEYVAULT_PERMISSIONS_SETUP.md](KEYVAULT_PERMISSIONS_SETUP.md) — RBAC permission setup

---

**Last Updated**: February 23, 2026  
**Status**: ✅ Working — Azure AD authentication operational
