# Azure OpenAI Authentication Setup Guide

## Issue Fixed: January 28, 2026
**Problem**: AI classification stopped working after Key Vault migration (Jan 20) - "AI service temporarily unavailable" with pattern matching fallback.

## Root Causes Identified
1. **Key Vault migration didn't update authentication code** - `llm_classifier.py` still used API key auth
2. **Tenant mismatch** - Token from corporate tenant (72f988bf...) but OpenAI resource in different tenant
3. **Missing role assignment** - User account needed Cognitive Services OpenAI User role
4. **Wrong deployment name** - Key Vault had `gpt-4o-02` but actual deployment is `gpt-4o-standard`
5. **Wrong endpoint** - `.env` file had old East endpoint, overriding Key Vault North Central endpoint
6. **Configuration priority** - `.env` file took precedence over Key Vault

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

## Code Configuration

### llm_classifier.py - Azure AD Authentication
```python
# Lines 104-113: Tenant-specific authentication
if use_aad:
    from azure.identity import InteractiveBrowserCredential, get_bearer_token_provider
    
    # CRITICAL: Must specify tenant ID where OpenAI resource is registered
    credential = InteractiveBrowserCredential(
        tenant_id="16b3c013-d300-468d-ac64-7eda0820b6d3"  # fdpo.onmicrosoft.com
    )
    
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default"
    )
```

### ai_config.py - Configuration Fields
```python
@dataclass
class AzureOpenAIConfig:
    endpoint: str
    api_key: str  # Optional when use_aad=true
    api_version: str = "2024-08-01-preview"
    deployment: str = "gpt-4o-standard"  # Classification deployment
    use_aad: bool = True  # MUST be true (API keys disabled)
```

### keyvault_config.py - Secret Mappings
```python
SECRET_MAPPINGS = {
    "AZURE_OPENAI_ENDPOINT": "AZURE-OPENAI-ENDPOINT",
    "AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT": "AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "AZURE-OPENAI-EMBEDDING-DEPLOYMENT",
    "AZURE_OPENAI_USE_AAD": "AZURE-OPENAI-USE-AAD",
    # AZURE_OPENAI_API_KEY intentionally not in Key Vault
}
```

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

## Testing & Validation

### Quick Validation Script
```powershell
# 1. Check Key Vault configuration
python check_kv_config.py

# 2. Verify token tenant
python check_token_tenant.py
# Expected: Token Tenant: 16b3c013-d300-468d-ac64-7eda0820b6d3

# 3. Run comprehensive test
python test_ai_integration.py
# Expected: All steps pass, API call successful

# 4. Start app and test
.\start_app.ps1
# Navigate to http://127.0.0.1:5003 and submit test issue
# Expected: AI classification without yellow warning
```

### Expected Log Output (Success)
```
[LLMClassifier] 🚀 Initializing LLM Classifier...
[LLMClassifier] 📋 Configuration loaded:
[LLMClassifier]   Endpoint: https://OpenAI-bp-NorthCentral.openai.azure.com/
[LLMClassifier]   Use AAD: True
[LLMClassifier] 🔐 Setting up Azure AD authentication...
[LLMClassifier]   Tenant ID: 16b3c013-d300-468d-ac64-7eda0820b6d3
[LLMClassifier] ✅ Using Azure AD authentication
[LLMClassifier] ✅ Initialization complete!
```

---

## Azure Deployment Notes

When deployed to Azure App Service / Container Apps:
- Remove `tenant_id` parameter from `InteractiveBrowserCredential` (won't work in production)
- Use `ManagedIdentityCredential` or `DefaultAzureCredential` (will use managed identity)
- Managed identity `mi-gcs-dev` must have all required role assignments
- Key Vault configuration remains the same
- No `.env` file needed in Azure

---

## Summary of Changes Made

1. ✅ Updated `llm_classifier.py` to support Azure AD authentication with tenant ID
2. ✅ Updated `ai_config.py` to include `use_aad` field
3. ✅ Updated `keyvault_config.py` SECRET_MAPPINGS with OpenAI secrets
4. ✅ Updated Key Vault secrets with correct endpoint and deployment names
5. ✅ Assigned Cognitive Services OpenAI User role to user account
6. ✅ Removed `.env` file to prevent configuration conflicts
7. ✅ Updated `authenticate_interactive.py` with correct tenant ID
8. ✅ Created diagnostic scripts: `test_ai_integration.py`, `check_token_tenant.py`, `check_kv_config.py`

---

## Related Files
- Authentication: `llm_classifier.py`, `ai_config.py`, `authenticate_interactive.py`
- Configuration: `keyvault_config.py`, `.env.backup` (archived)
- Diagnostics: `test_ai_integration.py`, `check_token_tenant.py`, `check_kv_config.py`
- Documentation: `KEYVAULT_MIGRATION_COMPLETE.md`, `MANAGED_IDENTITY_DEPLOYMENT.md`

---

**Last Updated**: January 28, 2026  
**Status**: ✅ Working - AI classification operational with Azure AD authentication
