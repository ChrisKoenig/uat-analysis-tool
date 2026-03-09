"""
Shared Azure Credential Manager
================================
Single credential instance shared across ALL services:
  - ai_quality_evaluator.py (Azure OpenAI for quality scoring)
  - llm_classifier.py (Azure OpenAI for classification)
  - ado_integration.py (Azure DevOps for work items + TFT)

Why: Each service was independently creating InteractiveBrowserCredential,
causing 3 separate browser auth prompts and ~10s wasted per AzureCLI timeout.
Now we authenticate ONCE and share the credential everywhere.
"""

import os
import threading
import logging

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_credential = None
_credential_type = None  # "cli" or "browser"

# Scopes we need tokens for
COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
ADO_SCOPE = "499b84ac-1321-427f-aa17-267ca6975798/.default"
KEYVAULT_SCOPE = "https://vault.azure.net/.default"

def _get_tenant_id() -> str:
    """Read tenant ID from the active environment config."""
    env_val = os.environ.get("AZURE_TENANT_ID")
    if env_val:
        return env_val
    try:
        from shared.config import get_app_config
        return get_app_config().tenant_id
    except Exception:
        # Hard fallback — should only hit this if config package is missing
        return "16b3c013-d300-468d-ac64-7eda0820b6d3"

TENANT_ID: str = _get_tenant_id()


def get_credential():
    """
    Return a shared Azure credential (singleton).
    First call authenticates; subsequent calls return cached credential.
    
    Returns:
        Azure credential object (AzureCliCredential or InteractiveBrowserCredential)
    """
    global _credential, _credential_type
    
    if _credential is not None:
        return _credential
    
    with _lock:
        # Double-check after acquiring lock
        if _credential is not None:
            return _credential
        
        _credential, _credential_type = _create_credential()
        return _credential


def _create_credential():
    """
    Create a credential for Azure OpenAI / ADO.
    
    Priority order:
    1. ManagedIdentityCredential (production: AZURE_CLIENT_ID is set)
    2. AzureCliCredential (local dev if 'az login' is active)
    3. InteractiveBrowserCredential (local dev fallback)
    """
    import os
    import subprocess
    from azure.identity import (
        AzureCliCredential,
        InteractiveBrowserCredential,
        ManagedIdentityCredential,
    )

    # 1. Production: User-assigned Managed Identity
    managed_identity_client_id = os.environ.get('AZURE_CLIENT_ID')
    if managed_identity_client_id:
        try:
            import time as _t
            logger.info(f"[SharedAuth] Using Managed Identity (client_id: {managed_identity_client_id[:8]}...)")
            print(f"[SharedAuth] Using Managed Identity (client_id: {managed_identity_client_id[:8]}...)", flush=True)
            cred = ManagedIdentityCredential(client_id=managed_identity_client_id)
            print(f"[SharedAuth] MI credential object created — requesting token for {COGNITIVE_SCOPE}...", flush=True)
            _t0 = _t.time()
            cred.get_token(COGNITIVE_SCOPE)
            print(f"[SharedAuth] [OK] Managed Identity credential works ({_t.time()-_t0:.1f}s)", flush=True)
            return cred, "managed_identity"
        except Exception as e:
            logger.warning(f"[SharedAuth] Managed Identity failed: {e}")
            print(f"[SharedAuth] [WARN] Managed Identity failed ({_t.time()-_t0:.1f}s): {type(e).__name__}: {e} -- trying other methods", flush=True)

    # 2. Local dev: Quick check if Azure CLI is logged in (~0.5s vs ~10s timeout)
    try:
        import sys
        result = subprocess.run(
            ["az", "account", "show"],
            capture_output=True, timeout=5,
            shell=(sys.platform == "win32"),  # az is a .cmd on Windows
        )
        if result.returncode == 0:
            logger.info("[SharedAuth] Azure CLI is logged in — using CLI credential")
            print("[SharedAuth] Azure CLI is logged in — using CLI credential", flush=True)
            cred = AzureCliCredential(tenant_id=TENANT_ID)
            cred.get_token(COGNITIVE_SCOPE)
            print("[SharedAuth] [OK] Azure CLI credential works", flush=True)
            return cred, "cli"
        else:
            print(f"[SharedAuth] Azure CLI not logged in (rc={result.returncode})", flush=True)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[SharedAuth] Azure CLI skipped: {e}", flush=True)
    except Exception as e:
        print(f"[SharedAuth] Azure CLI credential failed: {e}", flush=True)

    # 3. Local dev: Interactive Browser (one-time prompt)
    try:
        from azure.identity import TokenCachePersistenceOptions
        logger.info("[SharedAuth] Opening browser for authentication...")
        print("[SharedAuth] Opening browser for one-time authentication...")
        cache_opts = TokenCachePersistenceOptions(name="gcs-shared-auth")
        cred = InteractiveBrowserCredential(
            tenant_id=TENANT_ID,
            cache_persistence_options=cache_opts,
        )
        cred.get_token(COGNITIVE_SCOPE)
        logger.info("[SharedAuth] [OK] Browser authentication successful")
        print("[SharedAuth] [OK] Browser authentication successful")
        return cred, "browser"
    except Exception as e:
        logger.error(f"[SharedAuth] Authentication failed: {e}")
        print(f"[SharedAuth] [ERROR] Authentication failed: {e}")
        raise


def get_credential_type() -> str:
    """Return the type of credential in use ('cli' or 'browser')."""
    return _credential_type or "unknown"


def warm_up():
    """
    Pre-authenticate in a background thread so the server starts immediately.
    If the user completes browser auth during startup, the first request will be instant.
    If not, the first request will trigger the auth prompt.
    """
    import threading
    
    def _bg_warm():
        import time as _t
        try:
            print(f"[SharedAuth/bg] Calling get_credential()...", flush=True)
            _t0 = _t.time()
            cred = get_credential()
            print(f"[SharedAuth/bg] get_credential() returned in {_t.time()-_t0:.1f}s (type: {_credential_type})", flush=True)
            print(f"[SharedAuth/bg] Pre-warming COGNITIVE token...", flush=True)
            _t0 = _t.time()
            cred.get_token(COGNITIVE_SCOPE)
            print(f"[SharedAuth/bg] ✅ Cognitive Services token ready ({_t.time()-_t0:.1f}s)", flush=True)
            try:
                _t0 = _t.time()
                cred.get_token(ADO_SCOPE)
                print(f"[SharedAuth/bg] ✅ Azure DevOps token ready ({_t.time()-_t0:.1f}s)", flush=True)
            except Exception as e2:
                print(f"[SharedAuth/bg] ⚠ ADO token skipped: {type(e2).__name__}: {e2}", flush=True)
            print("[SharedAuth/bg] 🚀 All credentials pre-warmed and ready", flush=True)
        except Exception as e:
            print(f"[SharedAuth/bg] ⚠ Pre-warm failed: {type(e).__name__}: {e}", flush=True)
    
    t = threading.Thread(target=_bg_warm, daemon=True, name="shared-auth-warmup")
    t.start()
    print("[SharedAuth] 🔐 Background auth started", flush=True)
