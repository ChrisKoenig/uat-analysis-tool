"""Get the tenant ID of the OpenAI resource"""
from azure.identity import InteractiveBrowserCredential
import requests

# Authenticate
credential = InteractiveBrowserCredential()

# Get subscription ID
subscription_id = "13267e8e-b8f0-41c3-ba3e-509b3c7c8482"

# Method 1: Use ARM REST API to get subscription details
try:
    token = credential.get_token('https://management.azure.com/.default')
    headers = {
        'Authorization': f'Bearer {token.token}',
        'Content-Type': 'application/json'
    }
    
    # Get subscription details
    url = f'https://management.azure.com/subscriptions/{subscription_id}?api-version=2022-12-01'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        sub_data = response.json()
        tenant_id = sub_data.get('tenantId')
        print(f"\n✅ Subscription Tenant ID: {tenant_id}")
        print(f"   Subscription Name: {sub_data.get('displayName')}")
        print(f"   Subscription ID: {sub_data.get('subscriptionId')}")
    else:
        print(f"❌ Error getting subscription: {response.status_code}")
        print(response.text)
        
    # Also get OpenAI resource details
    resource_group = "rg-gcs-dev"  # Update if different
    resource_name = "OpenAI-bp-NorthCentral"
    
    url = f'https://management.azure.com/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.CognitiveServices/accounts/{resource_name}?api-version=2023-05-01'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        resource_data = response.json()
        print(f"\n✅ OpenAI Resource Details:")
        print(f"   Name: {resource_data.get('name')}")
        print(f"   Location: {resource_data.get('location')}")
        print(f"   Resource Group: {resource_data.get('id', '').split('/')[4]}")
    else:
        print(f"\n⚠️ Could not get OpenAI resource (you may need to update the resource group name)")
        print(f"   Status: {response.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
