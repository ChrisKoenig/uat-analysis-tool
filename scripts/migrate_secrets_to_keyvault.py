"""
Migrate secrets from .env.azure to Azure Key Vault
Run this script once to upload secrets to Key Vault
"""
import os
from dotenv import load_dotenv
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Load environment variables
load_dotenv('.env.azure')

# Key Vault URI
KEY_VAULT_URI = "https://kv-gcs-dev-gg4a6y.vault.azure.net/"

# Secrets to migrate (env_var_name -> key_vault_secret_name)
SECRETS_TO_MIGRATE = {
    "AZURE_STORAGE_ACCOUNT_NAME": "azure-storage-account-name",
    "AZURE_STORAGE_CONNECTION_STRING": "azure-storage-connection-string",
    "AZURE_APP_INSIGHTS_INSTRUMENTATION_KEY": "azure-app-insights-instrumentation-key",
    "AZURE_APP_INSIGHTS_CONNECTION_STRING": "azure-app-insights-connection-string",
    "AZURE_CONTAINER_REGISTRY_PASSWORD": "azure-container-registry-password",
}

def migrate_secrets():
    """Upload secrets from .env.azure to Key Vault"""
    print(f"Connecting to Key Vault: {KEY_VAULT_URI}")
    
    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=KEY_VAULT_URI, credential=credential)
        
        print("\n=== Migrating Secrets to Key Vault ===\n")
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for env_var, secret_name in SECRETS_TO_MIGRATE.items():
            value = os.environ.get(env_var)
            
            if not value:
                print(f"⚠ SKIP: {env_var} not found in .env.azure")
                skipped += 1
                continue
            
            try:
                # Check if secret already exists
                try:
                    existing = client.get_secret(secret_name)
                    print(f"ℹ UPDATE: {secret_name} (already exists, updating...)")
                except:
                    print(f"✓ CREATE: {secret_name}")
                
                # Set the secret
                client.set_secret(secret_name, value)
                migrated += 1
                
            except Exception as e:
                print(f"✗ ERROR: Failed to set {secret_name}: {e}")
                errors += 1
        
        print(f"\n=== Migration Complete ===")
        print(f"✓ Migrated: {migrated}")
        print(f"⚠ Skipped:  {skipped}")
        print(f"✗ Errors:   {errors}")
        
        if errors == 0:
            print("\n✓ All secrets successfully migrated to Key Vault!")
            print("\nNext steps:")
            print("1. Update your code to use keyvault_config.py")
            print("2. Test that all services can retrieve secrets")
            print("3. Remove secrets from .env.azure (keep non-secret config)")
            print("4. Update .env.azure with only non-secret values")
        
    except Exception as e:
        print(f"\n✗ ERROR: Could not connect to Key Vault: {e}")
        print("\nMake sure you have:")
        print("1. Run 'az login' to authenticate")
        print("2. Proper access policy on the Key Vault")
        print("3. Required permissions: Get, List, Set secrets")
        return False
    
    return errors == 0


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("Azure Key Vault Secret Migration Tool")
    print("=" * 60)
    print()
    print("This will upload secrets from .env.azure to Key Vault:")
    print(f"  {KEY_VAULT_URI}")
    print()
    print("Secrets to migrate:")
    for env_var, secret_name in SECRETS_TO_MIGRATE.items():
        print(f"  • {env_var} -> {secret_name}")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        success = migrate_secrets()
        sys.exit(0 if success else 1)
    else:
        print("\nMigration cancelled.")
        sys.exit(0)
