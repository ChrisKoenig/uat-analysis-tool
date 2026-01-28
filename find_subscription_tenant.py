"""
Find the tenant for the OpenAI subscription
"""
from azure.identity import InteractiveBrowserCredential
from azure.mgmt.resource import SubscriptionClient

print("Finding tenant for subscription...")

# Authenticate and list subscriptions across all tenants
credential = InteractiveBrowserCredential()
sub_client = SubscriptionClient(credential)

target_sub_id = "13267e8e-b8f0-41c3-ba3e-509b3c7c8482"

try:
    # List all subscriptions
    for sub in sub_client.subscriptions.list():
        if sub.subscription_id == target_sub_id:
            print(f"\n✅ Found subscription!")
            print(f"   Name: {sub.display_name}")
            print(f"   ID: {sub.subscription_id}")
            print(f"   Tenant ID: {sub.tenant_id}")
            print(f"\nNow authenticate to this tenant:")
            print(f"   python authenticate_to_correct_tenant.py {sub.tenant_id}")
            break
    else:
        print(f"❌ Subscription {target_sub_id} not found in accessible tenants")
        print("\nTry listing all your subscriptions:")
        for sub in sub_client.subscriptions.list():
            print(f"   {sub.display_name} ({sub.subscription_id}) - Tenant: {sub.tenant_id}")
            
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
