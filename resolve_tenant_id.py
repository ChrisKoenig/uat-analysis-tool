"""Resolve tenant ID from domain name"""
import requests

domain = "fdpo.onmicrosoft.com"

# Use OpenID configuration endpoint to get tenant ID
url = f"https://login.microsoftonline.com/{domain}/.well-known/openid-configuration"

try:
    response = requests.get(url)
    if response.status_code == 200:
        config = response.json()
        # Extract tenant ID from token_endpoint or issuer
        token_endpoint = config.get('token_endpoint', '')
        if token_endpoint:
            # Format: https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token
            tenant_id = token_endpoint.split('/')[3]
            print(f"✅ Resolved Tenant ID: {tenant_id}")
            print(f"   Domain: {domain}")
            print(f"   Issuer: {config.get('issuer', 'N/A')}")
        else:
            print("❌ Could not extract tenant ID from response")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"❌ Error: {e}")
