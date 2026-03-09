"""Update OpenAI deployment name in Key Vault to match actual deployment"""
from azure.identity import InteractiveBrowserCredential
from azure.keyvault.secrets import SecretClient

# Authenticate to the correct tenant
credential = InteractiveBrowserCredential(
    tenant_id="16b3c013-d300-468d-ac64-7eda0820b6d3"
)

# Connect to Key Vault
vault_url = "https://kv-gcs-dev-gg4a6y.vault.azure.net/"
client = SecretClient(vault_url=vault_url, credential=credential)

print("Updating OpenAI deployment names in Key Vault...")
print("=" * 80)

# Update classification deployment
try:
    client.set_secret("AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT", "gpt-4o-standard")
    print("✅ Updated AZURE-OPENAI-CLASSIFICATION-DEPLOYMENT to: gpt-4o-standard")
except Exception as e:
    print(f"❌ Failed to update classification deployment: {e}")

# Verify embedding deployment is correct
try:
    secret = client.get_secret("AZURE-OPENAI-EMBEDDING-DEPLOYMENT")
    print(f"✅ AZURE-OPENAI-EMBEDDING-DEPLOYMENT is: {secret.value}")
    if secret.value != "text-embedding-3-large":
        client.set_secret("AZURE-OPENAI-EMBEDDING-DEPLOYMENT", "text-embedding-3-large")
        print("   Updated to: text-embedding-3-large")
except Exception as e:
    print(f"❌ Failed to check embedding deployment: {e}")

print("=" * 80)
print("✅ Key Vault secrets updated!")
print("\nNow run: python test_ai_integration.py")
