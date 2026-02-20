"""
Azure Key Vault Configuration Module
Centralized secret management for GCS application

Supports both local development (DefaultAzureCredential) and 
production deployment (ManagedIdentityCredential).
"""
import os
from functools import lru_cache
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from typing import Optional

# Key Vault URI
KEY_VAULT_URI = "https://kv-gcs-dev-gg4a6y.vault.azure.net/"


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
SECRET_MAPPINGS = {
    "AZURE_STORAGE_ACCOUNT_NAME": "azure-storage-account-name",
    "AZURE_STORAGE_CONNECTION_STRING": "azure-storage-connection-string",
    "AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY": "azure-app-insights-instrumentation-key",
    "AZURE_APP_INSIGHTS_CONNECTION_STRING": "azure-app-insights-connection-string",
    "AZURE_CONTAINER_REGISTRY_PASSWORD": "azure-container-registry-password",
    "AZURE_OPENAI_ENDPOINT": "AZURE-OPENAI-ENDPOINT",
    "AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT": "AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "AZURE-OPENAI-EMBEDDING-DEPLOYMENT",
    "AZURE_OPENAI_API_KEY": "AZURE-OPENAI-API-KEY",
    "AZURE_OPENAI_USE_AAD": "AZURE-OPENAI-USE-AAD",
    "COSMOS_ENDPOINT": "COSMOS-ENDPOINT",
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
                # Check if managed identity is configured
                managed_identity_client_id = os.environ.get('AZURE_CLIENT_ID')
                
                if managed_identity_client_id:
                    # Production: Use managed identity
                    self._credential = ManagedIdentityCredential(client_id=managed_identity_client_id)
                    auth_method = f"Managed Identity (client_id: {managed_identity_client_id[:8]}...)"
                else:
                    # Development: Exclude slow-failing CLI/PowerShell credentials
                    # (saves ~20s when az/pwsh are not logged in)
                    self._credential = DefaultAzureCredential(
                        exclude_cli_credential=True,
                        exclude_powershell_credential=True,
                    )
                    auth_method = "DefaultAzureCredential (excl CLI/PowerShell)"
                
                self._client = SecretClient(vault_url=KEY_VAULT_URI, credential=self._credential)
                print(f"[OK] Connected to Key Vault: {KEY_VAULT_URI} ({_t.time()-_t0:.1f}s)")
                print(f"  Authentication: {auth_method}")
            except Exception as e:
                print(f"[WARNING] Could not connect to Key Vault: {e}")
                print("  Falling back to environment variables from .env.azure")
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
                    return value
            except Exception as e:
                print(f"[WARNING] Could not retrieve '{secret_name}' from Key Vault: {e}")
        
        # Fallback to environment variable
        if fallback_to_env:
            value = os.environ.get(env_var_name)
            if value:
                self._cache[env_var_name] = value
                return value
        
        return None
    
    def get_config(self) -> dict:
        """
        Get all configuration values for the application
        Returns dict with all secrets populated
        """
        config = {
            # Storage
            "AZURE_STORAGE_ACCOUNT_NAME": self.get_secret("AZURE_STORAGE_ACCOUNT_NAME"),
            "AZURE_STORAGE_CONNECTION_STRING": self.get_secret("AZURE_STORAGE_CONNECTION_STRING"),
            
            # Application Insights
            "AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY": self.get_secret("AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY"),
            "AZURE_APP_INSIGHTS_CONNECTION_STRING": self.get_secret("AZURE_APP_INSIGHTS_CONNECTION_STRING"),
            
            # Container Registry
            "AZURE_CONTAINER_REGISTRY_NAME": os.environ.get("AZURE_CONTAINER_REGISTRY_NAME"),
            "AZURE_CONTAINER_REGISTRY_SERVER": os.environ.get("AZURE_CONTAINER_REGISTRY_SERVER"),
            "AZURE_CONTAINER_REGISTRY_USERNAME": os.environ.get("AZURE_CONTAINER_REGISTRY_USERNAME"),
            "AZURE_CONTAINER_REGISTRY_PASSWORD": self.get_secret("AZURE_CONTAINER_REGISTRY_PASSWORD"),
            
            # Key Vault (non-secret)
            "AZURE_KEY_VAULT_NAME": os.environ.get("AZURE_KEY_VAULT_NAME", "kv-gcs-dev-gg4a6y"),
            "AZURE_KEY_VAULT_URI": KEY_VAULT_URI,
            
            # Log Analytics (non-secret)
            "AZURE_LOG_ANALYTICS_WORKSPACE_ID": os.environ.get("AZURE_LOG_ANALYTICS_WORKSPACE_ID"),
            
            # Container Apps (non-secret)
            "AZURE_CONTAINER_APPS_ENVIRONMENT": os.environ.get("AZURE_CONTAINER_APPS_ENVIRONMENT"),
            
            # Azure OpenAI (using Azure AD, no API key needed)
            "AZURE_OPENAI_RESOURCE_NAME": os.environ.get("AZURE_OPENAI_RESOURCE_NAME"),
            "AZURE_OPENAI_ENDPOINT": self.get_secret("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_USE_AAD": self.get_secret("AZURE_OPENAI_USE_AAD") or "true",
            "AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT": self.get_secret("AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT"),
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": self.get_secret("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
            "AZURE_OPENAI_API_KEY": self.get_secret("AZURE_OPENAI_API_KEY"),
            "AZURE_OPENAI_DEPLOYMENT_NAME": os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME": os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"),
            
            # Azure DevOps (using Azure CLI authentication)
            "ADO_ORGANIZATION": os.environ.get("ADO_ORGANIZATION"),
            "ADO_PROJECT": os.environ.get("ADO_PROJECT"),
        }
        
        return config
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """
        Validate that all required secrets are available
        Returns (is_valid, list_of_missing_secrets)
        """
        required_secrets = [
            "AZURE_STORAGE_CONNECTION_STRING",
        ]
        
        missing = []
        for secret in required_secrets:
            if not self.get_secret(secret):
                missing.append(secret)
        
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
