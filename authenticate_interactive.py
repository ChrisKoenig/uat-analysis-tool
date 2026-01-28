"""
Interactive Browser Authentication
This will open a browser window for you to authenticate with Azure
"""

from azure.identity import InteractiveBrowserCredential
from azure.keyvault.secrets import SecretClient
import sys

print("=" * 80)
print("Interactive Azure Authentication")
print("=" * 80)
print("\nA browser window will open for you to sign in with your Microsoft account.")
print("Please sign in with: bprice@microsoft.com")
print("Authenticating to: Microsoft Non-Production tenant")
print("=" * 80)

try:
    # Create interactive credential for Microsoft Non-Production tenant
    # Tenant ID: 16b3c013-d300-468d-ac64-7eda0820b6d3 (fdpo.onmicrosoft.com)
    credential = InteractiveBrowserCredential(
        tenant_id="16b3c013-d300-468d-ac64-7eda0820b6d3"
    )
    
    print("\nAuthenticating...")
    # Get token for Azure Management to access subscription
    mgmt_token = credential.get_token("https://management.azure.com/.default")
    
    # Get token for Cognitive Services (OpenAI)
    openai_token = credential.get_token(
        "https://cognitiveservices.azure.com/.default"
    )
    print("✅ Authentication successful!")
    
    # Test Key Vault access
    print("\nTesting Key Vault access...")
    client = SecretClient(
        vault_url="https://kv-gcs-dev-gg4a6y.vault.azure.net/",
        credential=credential
    )
    
    # Try to read a secret
    secret = client.get_secret("AZURE-OPENAI-ENDPOINT")
    print(f"✅ Key Vault access confirmed: {secret.value}")
    
    print("\n" + "=" * 80)
    print("✅ Authentication Complete!")
    print("=" * 80)
    print("\nYour credentials are now cached.")
    print("Run: python test_ai_integration.py")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ Authentication failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
