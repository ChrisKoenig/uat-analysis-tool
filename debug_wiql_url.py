"""Debug WIQL URL construction and test the actual HTTP call."""
import requests
from urllib.parse import quote
from ado_integration import AzureDevOpsConfig

# Get TFT credential (should be cached from prior run)
print("Getting TFT credential...")
cred = AzureDevOpsConfig.get_tft_credential()
token = cred.get_token(AzureDevOpsConfig.ADO_SCOPE).token
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

tft_org = "unifiedactiontracker"
tft_project = "Technical Feedback"

# Test 1: Verify projects endpoint still works
url1 = f"https://dev.azure.com/{tft_org}/_apis/projects?api-version=7.0"
r1 = requests.get(url1, headers=headers, timeout=15)
print(f"\n1. Projects API: {r1.status_code}")
if r1.status_code == 200:
    for p in r1.json().get("value", []):
        print(f"   - {p['name']} (id={p['id']})")

# Test 2: WIQL with quote() encoding
url2 = f"https://dev.azure.com/{tft_org}/{quote(tft_project)}/_apis/wit/wiql?api-version=7.0&$top=5"
wiql = {"query": "SELECT [System.Id] FROM workitems WHERE [System.TeamProject] = 'Technical Feedback' AND [System.WorkItemType] = 'Feature' ORDER BY [System.ChangedDate] DESC"}
r2 = requests.post(url2, headers=headers, json=wiql, timeout=15)
print(f"\n2. WIQL (quote encoded '{quote(tft_project)}'): {r2.status_code}")
if r2.status_code != 200:
    print(f"   Body: {r2.text[:500]}")
else:
    items = r2.json().get("workItems", [])
    print(f"   Work items found: {len(items)}")

# Test 3: WIQL without encoding (raw space)
url3 = f"https://dev.azure.com/{tft_org}/Technical Feedback/_apis/wit/wiql?api-version=7.0&$top=5"
r3 = requests.post(url3, headers=headers, json=wiql, timeout=15)
print(f"\n3. WIQL (raw space): {r3.status_code}")
if r3.status_code != 200:
    print(f"   Body: {r3.text[:500]}")
else:
    items = r3.json().get("workItems", [])
    print(f"   Work items found: {len(items)}")

# Test 4: WIQL with project ID instead of name
if r1.status_code == 200:
    tf_project = next((p for p in r1.json()["value"] if p["name"] == "Technical Feedback"), None)
    if tf_project:
        pid = tf_project["id"]
        url4 = f"https://dev.azure.com/{tft_org}/{pid}/_apis/wit/wiql?api-version=7.0&$top=5"
        r4 = requests.post(url4, headers=headers, json=wiql, timeout=15)
        print(f"\n4. WIQL (project ID '{pid}'): {r4.status_code}")
        if r4.status_code != 200:
            print(f"   Body: {r4.text[:500]}")
        else:
            items = r4.json().get("workItems", [])
            print(f"   Work items found: {len(items)}")

# Test 5: WIQL without project in URL (org-level)
url5 = f"https://dev.azure.com/{tft_org}/_apis/wit/wiql?api-version=7.0&$top=5"
r5 = requests.post(url5, headers=headers, json=wiql, timeout=15)
print(f"\n5. WIQL (org-level, no project in URL): {r5.status_code}")
if r5.status_code != 200:
    print(f"   Body: {r5.text[:500]}")
else:
    items = r5.json().get("workItems", [])
    print(f"   Work items found: {len(items)}")
