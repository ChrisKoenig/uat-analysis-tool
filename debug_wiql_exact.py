"""Replicate EXACTLY what search_tft_features() does, step by step."""
import requests
from urllib.parse import quote
from ado_integration import AzureDevOpsClient, AzureDevOpsConfig

print("Step 1: Create AzureDevOpsClient (triggers main org auth)...")
client = AzureDevOpsClient()
print(f"  Main org headers type: {type(client.headers)}")

print("\nStep 2: Get TFT credential and token...")
credential = client.config.get_tft_credential()
token = credential.get_token(client.config.ADO_SCOPE).token
print(f"  Token length: {len(token)}")

tft_headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

tft_org = "unifiedactiontracker"
tft_project = "Technical Feedback"
tft_base_url = f"https://dev.azure.com/{tft_org}"

# Test with simple WIQL first
wiql_query = """
SELECT [System.Id], [System.Title]
FROM workitems
WHERE [System.TeamProject] = 'Technical Feedback'
AND [System.WorkItemType] = 'Feature'
ORDER BY [System.ChangedDate] DESC
"""

wiql_url = f"{tft_base_url}/{quote(tft_project)}/_apis/wit/wiql?api-version={client.config.API_VERSION}&$top=5"
print(f"\nStep 3: WIQL query URL: {wiql_url}")
print(f"  Query: {wiql_query.strip()}")

r = requests.post(wiql_url, headers=tft_headers, json={'query': wiql_query})
print(f"  Response: {r.status_code}")
if r.status_code == 200:
    items = r.json().get('workItems', [])
    print(f"  Work items found: {len(items)}")
    for wi in items[:3]:
        print(f"    ID: {wi['id']}")
else:
    print(f"  Error body: {r.text[:500]}")

# Now test the full WIQL with filter
print("\nStep 4: Full WIQL with 'Premium Files' filter...")
full_query = """
SELECT [System.Id], [System.Title], [System.Description], [System.ChangedDate], [System.State]
FROM workitems
WHERE [System.TeamProject] = 'Technical Feedback'
AND [System.WorkItemType] = 'Feature'
AND [System.ChangedDate] >= '2024-03-06'
AND [System.State] <> 'Closed'
AND [System.Title] CONTAINS 'Premium Files'
ORDER BY [System.ChangedDate] DESC
"""

r2 = requests.post(wiql_url, headers=tft_headers, json={'query': full_query})
print(f"  Response: {r2.status_code}")
if r2.status_code == 200:
    items = r2.json().get('workItems', [])
    print(f"  Work items found: {len(items)}")
    for wi in items[:5]:
        print(f"    ID: {wi['id']}")
else:
    print(f"  Error body: {r2.text[:500]}")
