"""
Add Azure OpenAI secrets to Key Vault using Python
This bypasses Azure CLI conditional access restrictions
"""

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import sys

print("=" * 80)
print("Adding Azure OpenAI Configuration to Key Vault (Python)")
print("=" * 80)

# Key Vault configuration
VAULT_URL = "https://kv-gcs-dev-gg4a6y.vault.azure.net/"

# Azure OpenAI configuration
secrets_to_add = {
    "AZURE-OPENAI-ENDPOINT": "https://OpenAI-bp-NorthCentral.openai.azure.com/",
    "AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT": "gpt-4o-02",
    "AZURE-OPENAI-EMBEDDING-DEPLOYMENT": "text-embedding-3-large"
}

print(f"\nVault URL: {VAULT_URL}")
print(f"Secrets to add: {len(secrets_to_add)}")
print("\nNote: Using Azure AD authentication (no API key needed)")
print("AZURE_OPENAI_USE_AAD is already set to 'true' in Key Vault\n")

try:
    # Create credential and client
    print("Authenticating with DefaultAzureCredential...")
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)
    print("✅ Connected to Key Vault\n")
    
    # Add each secret
    print("Adding secrets...")
    for secret_name, secret_value in secrets_to_add.items():
        try:
            print(f"   {secret_name}...", end=" ")
            client.set_secret(secret_name, secret_value)
            print("✅ Set")
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    print("\n" + "=" * 80)
    print("✅ Configuration Complete!")
    print("=" * 80)
    print("\nSecrets added to Key Vault:")
    for secret_name, secret_value in secrets_to_add.items():
        display_value = secret_value[:50] + "..." if len(secret_value) > 50 else secret_value
        print(f"   {secret_name}: {display_value}")
    
    print("\nNext steps:")
    print("   1. Run: python test_ai_integration.py")
    print("   2. If test passes, restart: .\\start_app.ps1")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
