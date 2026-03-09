"""Assign Cognitive Services OpenAI User role to your user account"""

# Your user principal ID: f1a846d2-dca1-4402-b526-e5b3e5643bb7
# OpenAI Resource: OpenAI-bp-NorthCentral
# Subscription: 13267e8e-b8f0-41c3-ba3e-509b3c7c8482
# Resource Group: rg-gcs-dev (adjust if needed)

print("""
================================================================================
ROLE ASSIGNMENT NEEDED
================================================================================

Your user account needs the 'Cognitive Services OpenAI User' role.

To assign the role:

1. Go to Azure Portal → OpenAI-bp-NorthCentral
2. Click 'Access control (IAM)'
3. Click '+ Add' → 'Add role assignment'
4. Select role: 'Cognitive Services OpenAI User'
5. Click Next
6. Click '+ Select members'
7. Search for: Brad.Price@microsoft.com
8. Select your account and click 'Select'
9. Click 'Review + assign' twice

OR run this Azure CLI command:

az role assignment create \\
    --role "Cognitive Services OpenAI User" \\
    --assignee f1a846d2-dca1-4402-b526-e5b3e5643bb7 \\
    --scope /subscriptions/13267e8e-b8f0-41c3-ba3e-509b3c7c8482/resourceGroups/rg-gcs-dev/providers/Microsoft.CognitiveServices/accounts/OpenAI-bp-NorthCentral

================================================================================
Note: You already have 'Owner' at the subscription level, but you need the
specific OpenAI data plane role for API access.
================================================================================
""")
