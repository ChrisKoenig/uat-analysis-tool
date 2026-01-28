"""Check current token tenant"""
from azure.identity import InteractiveBrowserCredential
import jwt

# Create credential with specific tenant (Microsoft Non-Production)
cred = InteractiveBrowserCredential(
    tenant_id="16b3c013-d300-468d-ac64-7eda0820b6d3"
)
token = cred.get_token('https://management.azure.com/.default')

# Decode token
decoded = jwt.decode(token.token, options={'verify_signature': False})

print(f"Token Tenant: {decoded.get('tid', 'Not found')}")
print(f"User: {decoded.get('upn', decoded.get('email', 'Not found'))}")
