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

TENANT_ID = "16b3c013-d300-468d-ac64-7eda0820b6d3"


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
            logger.info(f"[SharedAuth] Using Managed Identity (client_id: {managed_identity_client_id[:8]}...)")
            print(f"[SharedAuth] 🔒 Using Managed Identity (client_id: {managed_identity_client_id[:8]}...)")
            cred = ManagedIdentityCredential(client_id=managed_identity_client_id)
            cred.get_token(COGNITIVE_SCOPE)
            print("[SharedAuth] ✅ Managed Identity credential works")
            return cred, "managed_identity"
        except Exception as e:
            logger.warning(f"[SharedAuth] Managed Identity failed: {e}")
            print(f"[SharedAuth] ⚠️ Managed Identity failed: {e} — trying other methods")

    # 2. Local dev: Quick check if Azure CLI is logged in (~0.5s vs ~10s timeout)
    try:
        result = subprocess.run(
            ["az", "account", "show"],
            capture_output=True, timeout=2,
        )
        if result.returncode == 0:
            logger.info("[SharedAuth] Azure CLI is logged in — using CLI credential")
            print("[SharedAuth] Azure CLI is logged in — using CLI credential")
            cred = AzureCliCredential()
            cred.get_token(COGNITIVE_SCOPE)
            print("[SharedAuth] ✅ Azure CLI credential works")
            return cred, "cli"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # az not installed or too slow — skip
    except Exception:
        pass

    # 3. Local dev: Interactive Browser (one-time prompt)
    try:
        logger.info("[SharedAuth] Opening browser for authentication...")
        print("[SharedAuth] 🌐 Opening browser for one-time authentication...")
        cred = InteractiveBrowserCredential(tenant_id=TENANT_ID)
        cred.get_token(COGNITIVE_SCOPE)
        logger.info("[SharedAuth] ✅ Browser authentication successful")
        print("[SharedAuth] ✅ Browser authentication successful")
        return cred, "browser"
    except Exception as e:
        logger.error(f"[SharedAuth] ❌ Authentication failed: {e}")
        print(f"[SharedAuth] ❌ Authentication failed: {e}")
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
        try:
            cred = get_credential()
            print(f"[SharedAuth] Pre-warming tokens (type: {_credential_type})...")
            cred.get_token(COGNITIVE_SCOPE)
            print("[SharedAuth] ✅ Cognitive Services token ready")
            try:
                cred.get_token(ADO_SCOPE)
                print("[SharedAuth] ✅ Azure DevOps token ready")
            except Exception:
                print("[SharedAuth] ⚠ ADO token pre-warm skipped (may need separate org auth)")
            print("[SharedAuth] 🚀 All credentials pre-warmed and ready")
        except Exception as e:
            print(f"[SharedAuth] ⚠ Pre-warm failed (will authenticate on first request): {e}")
    
    t = threading.Thread(target=_bg_warm, daemon=True, name="shared-auth-warmup")
    t.start()
    print("[SharedAuth] 🔐 Background auth started — check your browser if prompted")
