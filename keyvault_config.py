"""
Azure Key Vault Configuration Module
Centralized secret management for GCS application

Supports both local development (DefaultAzureCredential) and 
production deployment (ManagedIdentityCredential).
"""
import os
import logging
from functools import lru_cache
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from typing import Optional

logger = logging.getLogger("keyvault_config")

# Key Vault URI — resolved from env vars, then from the active environment config.
def _resolve_kv_name() -> str:
    name = os.environ.get("KEY_VAULT_NAME") or os.environ.get("AZURE_KEY_VAULT_NAME")
    if name:
        return name
    try:
        from config import get_app_config
        return get_app_config().key_vault_name
    except Exception:
        # Last-resort fallback so imports never blow up — logged as a warning.
        import warnings
        warnings.warn(
            "KEY_VAULT_NAME not set and config package unavailable; "
            "falling back to dev Key Vault. Set APP_ENV and KEY_VAULT_NAME.",
            RuntimeWarning,
            stacklevel=2,
        )
        return "kv-gcs-dev-gg4a6y"

_kv_name = _resolve_kv_name()
KEY_VAULT_URI = f"https://{_kv_name}.vault.azure.net/"


# ── TODO: REMOVE before pre-prod deployment ──────────────────────────────
# This check exists because corporate policy disables KeyVault network
# access after 6 hours of inactivity in the dev environment.  In pre-prod
# the vault is always reachable via private endpoint / managed identity,
# so this function (and the startup call in main.py) can be deleted.
# ──────────────────────────────────────────────────────────────────────────
def check_reachable(timeout_seconds: float = 3.0) -> tuple[bool, str]:
    """
    Quick TCP probe to see if the Key Vault HTTPS endpoint is reachable.
    Returns (is_reachable, message).
    """
    import socket
    from urllib.parse import urlparse
    host = urlparse(KEY_VAULT_URI).hostname  # e.g. kv-gcs-dev-gg4a6y.vault.azure.net
    try:
        sock = socket.create_connection((host, 443), timeout=timeout_seconds)
        sock.close()
        return True, f"Key Vault reachable ({host}:443)"
    except OSError as e:
        return False, (
            f"\n{'='*64}\n"
            f"  ⚠️  KEY VAULT UNREACHABLE  ({host}:443)\n"
            f"  {e}\n\n"
            f"  Your company policy may have disabled network access.\n"
            f"  Re-enable it in the Azure Portal → Key Vault →\n"
            f"  Networking → Firewalls and virtual networks.\n"
            f"  (Secrets will fall back to .env / environment variables)\n"
            f"{'='*64}"
        )


# Secret name mappings (Key Vault doesn't allow underscores, using hyphens)
# Only TRUE secrets (credentials / keys) belong here.
# Configuration values (endpoints, deployment names, flags) live in
# config/environments/*.json and are accessed via get_app_config().
SECRET_MAPPINGS = {
    # Application Insights (contains ingestion keys)
    "AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY": "azure-app-insights-instrumentation-key",
    "AZURE_APP_INSIGHTS_CONNECTION_STRING": "azure-app-insights-connection-string",
    # Azure OpenAI (API key — only needed when NOT using AAD auth)
    "AZURE_OPENAI_API_KEY": "AZURE-OPENAI-API-KEY",
    # Cosmos DB (account key — only needed when NOT using AAD auth)
    "COSMOS_KEY": "COSMOS-KEY",
}


class KeyVaultConfig:
    """Manages secrets from Azure Key Vault with fallback to environment variables"""
    
    def __init__(self):
        self._client: Optional[SecretClient] = None
        self._credential = None
        self._cache = {}
        
    def _get_client(self) -> SecretClient:
        """
        Lazy initialization of Key Vault client
        
        Uses ManagedIdentityCredential if AZURE_CLIENT_ID is set (production),
        otherwise uses DefaultAzureCredential (local development).
        
        Excludes AzureCliCredential and AzurePowerShellCredential in dev mode
        to avoid ~20s of timeouts when az/pwsh are not logged in.
        """
        if self._client is None:
            try:
                import time as _t
                _t0 = _t.time()
                managed_identity_client_id = os.environ.get('AZURE_CLIENT_ID')
                
                if managed_identity_client_id:
                    self._credential = ManagedIdentityCredential(client_id=managed_identity_client_id)
                    auth_method = f"Managed Identity ({managed_identity_client_id[:8]}...)"
                else:
                    self._credential = DefaultAzureCredential()
                    auth_method = "DefaultAzureCredential"
                
                self._client = SecretClient(vault_url=KEY_VAULT_URI, credential=self._credential)
                logger.info("Key Vault ready: %s (%s, %.1fs)", KEY_VAULT_URI, auth_method, _t.time()-_t0)
            except Exception as e:
                logger.warning("Could not connect to Key Vault: %s — falling back to config", e)
        return self._client
    
    def get_secret(self, env_var_name: str, fallback_to_env: bool = True) -> Optional[str]:
        """
        Get secret from Key Vault with fallback to environment variable
        
        Args:
            env_var_name: Environment variable name (e.g., 'AZURE_STORAGE_ACCOUNT_NAME')
            fallback_to_env: If True, fallback to os.environ if Key Vault fails
            
        Returns:
            Secret value or None
        """
        # Check cache first
        if env_var_name in self._cache:
            return self._cache[env_var_name]
        
        # Try Key Vault
        secret_name = SECRET_MAPPINGS.get(env_var_name)
        if secret_name:
            try:
                client = self._get_client()
                if client:
                    secret = client.get_secret(secret_name)
                    value = secret.value
                    self._cache[env_var_name] = value
                    logger.debug("KV secret '%s' retrieved", secret_name)
                    return value
            except Exception as e:
                err_name = type(e).__name__
                if "NotFound" in err_name or "ResourceNotFoundError" in err_name:
                    logger.debug("KV secret '%s' not found — using config fallback", secret_name)
                else:
                    logger.warning("KV secret '%s' failed: %s", secret_name, e)
        
        # Fallback to environment variable
        if fallback_to_env:
            value = os.environ.get(env_var_name)
            if value:
                self._cache[env_var_name] = value
                return value
                return value
        
        return None
    
    def get_config(self) -> dict:
        """
        Get all configuration values for the application.
        True secrets come from Key Vault; everything else from AppConfig.
        """
        try:
            from config import get_app_config
            _cfg = get_app_config()
        except Exception:
            _cfg = None

        config = {
            # ── True secrets (Key Vault) ──
            "AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY": self.get_secret("AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY"),
            "AZURE_APP_INSIGHTS_CONNECTION_STRING": self.get_secret("AZURE_APP_INSIGHTS_CONNECTION_STRING"),
            "AZURE_OPENAI_API_KEY": self.get_secret("AZURE_OPENAI_API_KEY"),

            # ── Configuration (AppConfig / env) ──
            "AZURE_KEY_VAULT_NAME": _kv_name,
            "AZURE_KEY_VAULT_URI": KEY_VAULT_URI,
            "AZURE_LOG_ANALYTICS_WORKSPACE_ID": os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID"),
            "AZURE_OPENAI_ENDPOINT": getattr(_cfg, 'openai_endpoint', None) if _cfg else os.environ.get("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_USE_AAD": "true",
            "AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT": getattr(_cfg, 'classification_deployment', None) if _cfg else os.environ.get("AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT"),
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": getattr(_cfg, 'embedding_deployment', None) if _cfg else os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            "COSMOS_ENDPOINT": getattr(_cfg, 'cosmos_endpoint', None) if _cfg else os.environ.get("COSMOS_ENDPOINT"),
            "ADO_ORGANIZATION": getattr(_cfg, 'ado_organization', None) if _cfg else os.environ.get("ADO_ORGANIZATION"),
            "ADO_PROJECT": getattr(_cfg, 'ado_project', None) if _cfg else os.environ.get("ADO_PROJECT"),
        }

        return config
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """
        Validate that required configuration is available.
        Checks AppConfig for config values; Key Vault only for true secrets.
        """
        missing = []
        try:
            from config import get_app_config
            cfg = get_app_config()
            if not getattr(cfg, 'cosmos_endpoint', None):
                missing.append("cosmos_account (in config JSON)")
            if not getattr(cfg, 'openai_endpoint', None):
                missing.append("openai_account (in config JSON)")
        except Exception:
            missing.append("AppConfig unavailable (check APP_ENV)")

        return len(missing) == 0, missing


# Global instance
_kv_config = None

def get_keyvault_config() -> KeyVaultConfig:
    """Get or create the global KeyVaultConfig instance"""
    global _kv_config
    if _kv_config is None:
        _kv_config = KeyVaultConfig()
    return _kv_config


# Convenience functions
def get_secret(name: str) -> Optional[str]:
    """Convenience function to get a secret"""
    return get_keyvault_config().get_secret(name)


def get_config() -> dict:
    """Convenience function to get all configuration"""
    return get_keyvault_config().get_config()


if __name__ == "__main__":
    # Test the configuration
    from dotenv import load_dotenv
    load_dotenv('.env.azure')
    
    config = get_keyvault_config()
    print("\n=== Testing Key Vault Configuration ===\n")
    
    # Test individual secret
    storage_account = config.get_secret("AZURE_STORAGE_ACCOUNT_NAME")
    print(f"Storage Account: {storage_account}")
    
    # Validate configuration
    is_valid, missing = config.validate_config()
    if is_valid:
        print("\n[OK] All required secrets are available")
    else:
        print(f"\n[WARNING] Missing required secrets: {', '.join(missing)}")
    
    # Get full configuration
    full_config = config.get_config()
    print(f"\n[OK] Loaded {len([v for v in full_config.values() if v])} configuration values")
