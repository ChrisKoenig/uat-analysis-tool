# Project Status - Intelligent Context Analysis System
**Last Updated**: February 3, 2026
**Status**: ✅ All systems operational - AI classification fully working

---

## Current Architecture

### Main Application
- **Web UI**: http://localhost:5003
- **Teams Bot**: http://localhost:3978/api/messages
- **Startup Script**: `.\start_app.ps1` (starts everything)

### Microservices (All ports working)
- API Gateway: 8000
- Context Analyzer: 8001
- Search Service: 8002
- Enhanced Matching: 8003
- UAT Management: 8004
- LLM Classifier: 8005
- Embedding Service: 8006
- Vector Search: 8007
- **Admin Portal: 8008** ⬅️ NEW

---

## Recent Changes (Jan 28, 2026) - CRITICAL FIXES ⚡

### **Azure OpenAI Authentication Overhaul** ✅
**Issue**: AI classification stopped working after Key Vault migration on Jan 20. System showing "AI service temporarily unavailable" with pattern matching fallback.

**Root Causes Identified**:
1. Key Vault migration didn't update `llm_classifier.py` authentication code
2. Token from wrong tenant (corporate 72f988bf... vs resource tenant 16b3c013...)
3. Missing Cognitive Services OpenAI User role on user account
4. Wrong deployment name in Key Vault (gpt-4o-02 vs actual gpt-4o-standard)
5. Wrong endpoint (.env had East, actual is North Central)
6. .env file overriding Key Vault configuration

**Fixes Applied**:
- ✅ Updated `llm_classifier.py` with Azure AD authentication (lines 100-140)
- ✅ Added tenant-specific InteractiveBrowserCredential (tenant: 16b3c013-d300-468d-ac64-7eda0820b6d3)
- ✅ Updated `ai_config.py` with `use_aad` field for authentication mode
- ✅ Updated `keyvault_config.py` to include OpenAI secrets mapping
- ✅ Assigned Cognitive Services OpenAI User role to Brad.Price@microsoft.com
- ✅ Corrected Key Vault secrets: deployment name and endpoint
- ✅ Removed .env file (renamed to .env.backup) to prevent override
- ✅ Fixed `authenticate_interactive.py` with correct tenant
- ✅ Updated `test_ai_integration.py` with tenant-specific credential
- ✅ Fixed `start_app.ps1` to handle None values from Key Vault

**Result**: AI classification now working perfectly (0.95 confidence, no fallback warnings)

**Documentation Created**:
- 📄 `AZURE_OPENAI_AUTH_SETUP.md` - Comprehensive authentication guide
- 📄 `AI_FIX_SUMMARY_2026-01-28.md` - Session summary with all changes
- 📄 Updated `README.md` with authentication documentation references

**Committed**: d4f52fd "Fix Azure OpenAI authentication and tenant configuration"

---

## Previous Changes (Jan 23, 2026)

### 1. **TFT Feature Search Fixes** ✅
- **Issue**: `'NoneType' object has no attribute 'search_tft_features'`
- **Fix**: Changed to use `get_ado_client()` for proper initialization
- **Location**: `app.py` line ~1634

### 2. **Azure OpenAI Timeout Fix** ✅
- **Issue**: Application hanging on embedding API calls
- **Fix**: Added 10-second timeout to AzureOpenAI client
- **Location**: `embedding_service.py` line ~30

### 3. **Dual Authentication Caching** ✅
- **Issue**: Two auth prompts every time (not cached)
- **Fix**: Added caching for both main + TFT credentials
- **Locations**: 
  - `ado_integration.py` lines 60-65 (credential variables)
  - `ado_integration.py` lines 140-170 (TFT credential caching)
- **Result**: Only 2 prompts on first run (expected), then cached

### 4. **Admin Portal Port Change** ✅
- **Issue**: Port 8004 conflict with UAT Management
- **Fix**: Moved admin portal to port 8008
- **Files Modified**: 
  - `admin_service.py` (port change)
  - `start_admin_service.ps1` (port + URLs)
  - `start_app.ps1` (integrated admin portal startup)

---

## Known Working Features

✅ Web UI with Quick ICA analysis
✅ Teams Bot integration
✅ TFT Feature search for feature_request category
✅ **Azure OpenAI AI classification (Azure AD auth)** ⬅️ FIXED Jan 28
✅ Dual organization authentication (main + TFT)
✅ Embedding service with cache fallback
✅ All 8 microservices + API Gateway
✅ Admin portal on port 8008

---

## Known Issues

⚠️ Admin portal shows "AuthorizationFailure" on blob storage access
- Error: "This request is not authorized to perform this operation"
- Likely needs managed identity or storage permissions fix
- Workaround: Use local JSON files for testing

---

## Authentication Architecture

### Azure OpenAI Authentication (UPDATED Jan 28, 2026)
**Resource**: OpenAI-bp-NorthCentral
**Location**: North Central US
**Endpoint**: https://OpenAI-bp-NorthCentral.openai.azure.com/
**Tenant**: Microsoft Non-Production (fdpo.onmicrosoft.com)
**Tenant ID**: 16b3c013-d300-468d-ac64-7eda0820b6d3
**Subscription**: MCAPS-Hybrid-REQ-53439-2023-bprice

**Authentication Method**: Azure AD only (API keys disabled by policy)
- **Local Development**: InteractiveBrowserCredential with tenant_id
- **Azure Deployment**: ManagedIdentityCredential (mi-gcs-dev)

**Deployments**:
- Classification: `gpt-4o-standard` (NOT gpt-4o-02!)
- Embeddings: `text-embedding-3-large` (3072 dimensions)

**Required Role**: Cognitive Services OpenAI User
- Assigned to: Brad.Price@microsoft.com
- For deployment: mi-gcs-dev managed identity

**Configuration Source**: Azure Key Vault (kv-gcs-dev-gg4a6y)
- Priority: Key Vault ONLY (.env removed to prevent override)
- Key Vault secrets: endpoint, deployment names, use_aad flag

**Quick Diagnostics**:
```powershell
python check_token_tenant.py      # Verify token tenant
python check_kv_config.py         # Verify Key Vault config
python test_ai_integration.py     # Full 6-step test
```

### Azure DevOps - Two Separate Organizations
1. **Main Org** (`unifiedactiontrackertest`)
   - Purpose: Work item creation
   - Method: Azure CLI or Interactive Browser
   - Cached in: `AzureDevOpsConfig._cached_credential`

2. **TFT Org** (`unifiedactiontracker/Technical Feedback`)
   - Purpose: Feature search
   - Method: Interactive Browser with MS tenant ID
   - Cached in: `AzureDevOpsConfig._cached_tft_credential`

Both prompt once on first use, then cached for session.

---

## Key Configuration

### Azure OpenAI
- **Endpoint**: https://OpenAI-bp-NorthCentral.openai.azure.com/ (Key Vault)
- **Authentication**: Azure AD with tenant 16b3c013-d300-468d-ac64-7eda0820b6d3
- **Models**:
  - Classification: `gpt-4o-standard` ⬅️ CORRECTED (was gpt-4o-02)
  - Embeddings: `text-embedding-3-large` (3072 dimensions)
- **Timeout**: 10 seconds (prevents hanging)
- **API Version**: 2024-08-01-preview

### Caching Strategy
- Cache TTL: 7 days
- Location: `cache/ai_cache/`
- Behavior: Use cache directly if < 3 days old

---

## Recent Backups

1. **backup_tft_auth_fixes_20260123_220315/** 
   - TFT authentication fixes
   - Timeout fixes
   - Pre-admin portal changes

2. **backup_admin_portal_8008_20260123_222155/**
   - All TFT fixes
   - Admin portal on 8008
   - Integrated into start_app.ps1
   - Full code documentation

3. **backup_keyvault_complete_20260120_142955/** ⬅️ KEY VAULT MIGRATION
   - Key Vault migration (triggered auth issues)

**Latest State**: All authentication fixes committed (d4f52fd) on Jan 28, 2026

---

## Important Files

### Core Application
- `app.py` - Main Flask web application
- `start_app.ps1` - Startup script for all services
- `ado_integration.py` - Azure DevOps integration with dual auth
- `embedding_service.py` - Azure OpenAI embeddings with timeout

### Configuration
- `ai_config.py` - Azure OpenAI configuration with `use_aad` field
- `keyvault_config.py` - Azure Key Vault integration with OpenAI secrets
- `.env.backup` - Old local variables (DISABLED to prevent Key Vault override)

### Authentication & Testing
- `authenticate_interactive.py` - Manual auth testing with tenant ID
- `test_ai_integration.py` - Comprehensive 6-step diagnostic
- `check_token_tenant.py` - Quick token tenant verification
- `check_kv_config.py` - Key Vault configuration check

### Documentation (Jan 28, 2026)
- `AZURE_OPENAI_AUTH_SETUP.md` - **Comprehensive authentication guide**
- `AI_FIX_SUMMARY_2026-01-28.md` - Session summary with all fixes

### Microservices
- `api_gateway.py` - Central routing (port 8000)
- `agents/*/service.py` - Individual microservices

### Admin
- `admin_service.py` - Admin portal (port 8008)
- `start_admin_service.ps1` - Admin portal startup

---

## Next Steps / TODO

- [ ] ~~Fix Azure OpenAI authentication~~ ✅ COMPLETED Jan 28
- [ ] Fix admin portal blob storage authorization
- [ ] Test managed identity (mi-gcs-dev) authentication in Azure deployment
- [ ] Monitor AI classification confidence levels over time
- [ ] Consider adding credential refresh logic for long sessions
- [ ] Monitor embedding API call patterns for optimization
- [ ] Add more comprehensive error handling for Azure OpenAI failures
- [ ] Document the full TFT search flow in architecture docs

---

## How to Start

```powershell
# Start everything (recommended)
.\start_app.ps1

# Start admin portal only (if needed separately)
.\start_admin_service.ps1

# Start individual services
cd agents\context-analyzer
python service.py
```

---

## Troubleshooting Quick Reference

### Azure OpenAI Issues (Added Jan 28, 2026)

**"AI service temporarily unavailable" / Pattern matching fallback**
- Issue: Azure AD authentication not configured or wrong tenant
- Fix: See AZURE_OPENAI_AUTH_SETUP.md for complete guide
- Quick check: `python check_token_tenant.py` (should show 16b3c013-d300-468d-ac64-7eda0820b6d3)

**"Token tenant does not match resource tenant"**
- Issue: Using wrong tenant for authentication
- Fix: Use InteractiveBrowserCredential with tenant_id="16b3c013-d300-468d-ac64-7eda0820b6d3"
- Location: `llm_classifier.py` lines 105-107

**"The principal lacks the required data action"**
- Issue: Missing Cognitive Services OpenAI User role
- Fix: Assign role to user account or managed identity in Azure portal
- Resource: OpenAI-bp-NorthCentral

**"DeploymentNotFound"**
- Issue: Wrong deployment name (case-sensitive!)
- Fix: Use `gpt-4o-standard` NOT `gpt-4o-02`
- Check: `python check_kv_config.py`

**"Wrong endpoint or configuration"**
- Issue: .env overriding Key Vault
- Fix: Rename .env to .env.backup (configuration should only come from Key Vault)

### Azure DevOps Issues

**"NoneType has no attribute"**
- Issue: ADO client not initialized
- Fix: Use `get_ado_client()` instead of global `ado_client`

**Application Hanging**
- Issue: Azure OpenAI timeout not set
- Fix: Already fixed - 10 second timeout in embedding_service.py

### Multiple Auth Prompts
- Issue: Credentials not cached
- Fix: Already fixed - both credentials now cached

### Port Conflicts
- Issue: Service already running on port
- Solution: Check port assignments in start_app.ps1
- Admin portal: 8008 (moved from 8004)

---

**STATUS**: System is stable and working. AI classification fully operational after Jan 28 authentication fixes. All major issues resolved and comprehensively documented.

**CRITICAL REFERENCE**: For any Azure OpenAI authentication issues, see `AZURE_OPENAI_AUTH_SETUP.md` first!
