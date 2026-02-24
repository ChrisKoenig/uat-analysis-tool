# Troubleshooting Guide

## Flask Server Exits Immediately in VS Code Terminals

**Issue:** Flask server starts successfully, authenticates, and then immediately exits with "Flask exited normally" when run from VS Code integrated terminals.

**Symptoms:**
- Flask shows "Running on http://127.0.0.1:5002" 
- Immediately followed by "[DEBUG] Flask exited normally"
- Process exits with code 1
- Same issue occurs with minimal test Flask apps
- Works fine in standalone PowerShell windows

**Root Cause:** VS Code's integrated terminal process management interferes with long-running Flask server processes. This is a known compatibility issue between VS Code terminals and Flask's blocking server process.

**Workaround (Required for Testing):**

### Starting Services for Testing:

**PowerShell Window 1 (Flask API):**
```powershell
cd C:\Projects\Hack
.\start_app.ps1
```

**PowerShell Window 2 (Teams Bot):**
```powershell
cd C:\Projects\Hack-TeamsBot
python bot.py
```

**Important:** Use standalone PowerShell windows (not VS Code terminals) for both services when testing bot workflows.

### What Works:
✅ Standalone PowerShell windows  
✅ Windows Terminal  
✅ CMD windows  
✅ Production deployment (WSGI servers like Gunicorn/Waitress)

### What Doesn't Work:
❌ VS Code integrated terminals  
❌ VS Code Python extension "Run Python File"

## Date Discovered
January 14, 2026

## Related Issues
- Flask runs but immediately exits after showing "Press CTRL+C to quit"
- No actual CTRL+C signal is sent
- app.run() returns immediately instead of blocking
- Issue persists even with `use_reloader=False` and `debug=False`

## Tested Solutions That Didn't Work
- Clearing Python cache (`__pycache__`)
- Reinstalling pandas/sklearn/numpy
- Different Flask configurations
- Using different port numbers
- Setting various Flask debug flags

## Why This Happens
VS Code's terminal multiplexer (which allows multiple terminals in tabs) can interfere with processes that:
1. Block indefinitely (like web servers)
2. Wait for network connections
3. Have long-running event loops

The terminal may send signals or close file descriptors that cause Flask to think it should shut down.

## Future Testing Protocol
1. **Always test bot workflows using standalone PowerShell windows**
2. For quick API tests, VS Code terminals may work
3. For full end-to-end testing, use external terminals
4. Document any similar issues with other long-running services

---

## Cosmos DB: Repeated Login Prompts / "Loading Dashboard" Stuck

**Date Discovered:** February 23, 2026

**Symptoms:**
- Triage UI stuck on "Loading dashboard…" forever
- Browser pops up Azure AD login prompts repeatedly (10+ times)
- API `/health` returns `"status":"degraded"` with `Forbidden` error mentioning IP address
- API data endpoints return empty `{"items":[],"count":0}` with a `"warning"` about firewall

**Root Cause:** Cosmos DB account `cosmos-gcs-dev` had `publicNetworkAccess` set to **Disabled**. This overrides ALL IP firewall rules — no public internet traffic gets through, even if your IP is in the allow list. The 403 Forbidden from Cosmos causes the Azure Identity SDK's `ChainedTokenCredential` to keep retrying `InteractiveBrowserCredential`, which pops up a browser login window each time.

**How to Diagnose:**
```powershell
# 1. Check API health — look for "Forbidden" / IP blocked error
curl -s http://localhost:8009/health

# 2. Check Cosmos DB public network access setting
az cosmosdb show --name cosmos-gcs-dev --resource-group rg-gcs-dev `
  --query "{publicNetworkAccess:publicNetworkAccess, ipRules:ipRules}" -o json
```

**Fix:**
```powershell
# Re-enable public network access (takes ~1-2 minutes)
az cosmosdb update --name cosmos-gcs-dev --resource-group rg-gcs-dev `
  --public-network-access ENABLED

# Verify
az cosmosdb show --name cosmos-gcs-dev --resource-group rg-gcs-dev `
  --query "publicNetworkAccess" -o tsv
# Should return: Enabled

# Then restart the API server so it reconnects
```

**If your IP changed** (e.g., after router restart):
```powershell
# Find current public IP
curl -s https://api.ipify.org

# Add it to Cosmos DB firewall
az cosmosdb update --name cosmos-gcs-dev --resource-group rg-gcs-dev `
  --ip-range-filter "104.42.195.92,40.76.54.131,52.176.6.30,52.169.50.45,52.187.184.26,0.0.0.0,<YOUR_NEW_IP>"
```

**Key Details:**
- Cosmos DB account: `cosmos-gcs-dev` in `rg-gcs-dev`
- Current allowed IP: `73.118.198.121`
- The `0.0.0.0` entry allows Azure Portal access
- The other IPs (`104.42.*`, `40.76.*`, etc.) are Azure data center IPs for portal features
- `publicNetworkAccess: Disabled` **blocks everything** regardless of IP rules
