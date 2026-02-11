"""
Phase 7 Integration Tests: UAT Management Service
Tests CRUD operations through the API Gateway
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
GATEWAY_UAT_URL = f"{BASE_URL}/api/uat"

def print_test_header(test_name):
    """Print formatted test header"""
    print("\n" + "="*80)
    print(f"🧪 TEST: {test_name}")
    print("="*80)

def print_result(success, message):
    """Print formatted test result"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")

def test_service_health():
    """Test 1: Verify all services are healthy"""
    print_test_header("Service Health Checks")
    
    services = {
        "Context Analyzer": 8001,
        "Search Service": 8002,
        "Enhanced Matching": 8003,
        "UAT Management": 8004,
        "API Gateway": 8000
    }
    
    all_healthy = True
    for name, port in services.items():
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=5)
            if response.status_code == 200:
                print_result(True, f"{name} (port {port}) is healthy")
            else:
                print_result(False, f"{name} (port {port}) returned {response.status_code}")
                all_healthy = False
        except Exception as e:
            print_result(False, f"{name} (port {port}) failed: {e}")
            all_healthy = False
    
    return all_healthy

def test_create_uat():
    """Test 2: Create a UAT work item"""
    print_test_header("Create UAT Work Item")
    
    try:
        payload = {
            "title": f"[TEST] Phase 7 Integration Test - {datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "description": "This is a test UAT created during Phase 7 integration testing. It verifies that the UAT Management microservice can successfully create work items in Azure DevOps through the API Gateway.",
            "impact": "This UAT tests the create functionality of the UAT Management service",
            "category": "feature_request",
            "intent": "test_automation",
            "classification_reason": "Integration test for Phase 7 UAT Management service"
        }
        
        print(f"📤 Sending create request to {GATEWAY_UAT_URL}/create")
        response = requests.post(f"{GATEWAY_UAT_URL}/create", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            work_item_id = result.get('work_item_id')
            if work_item_id:
                print_result(True, f"UAT created successfully: #{work_item_id}")
                print(f"   📋 Title: {result.get('title', 'N/A')}")
                print(f"   🔗 URL: {result.get('url', 'N/A')}")
                return work_item_id
            else:
                print_result(False, "No work_item_id in response")
                return None
        else:
            print_result(False, f"Request failed with status {response.status_code}")
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print_result(False, f"Exception occurred: {e}")
        return None

def test_get_uat(work_item_id):
    """Test 3: Retrieve UAT by ID"""
    print_test_header("Retrieve UAT Work Item")
    
    if not work_item_id:
        print_result(False, "No work_item_id provided (skipped)")
        return False
    
    try:
        print(f"📤 Sending get request to {GATEWAY_UAT_URL}/{work_item_id}")
        response = requests.get(f"{GATEWAY_UAT_URL}/{work_item_id}", timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            # Check if this is the full work item response with 'id' at root
            work_item_id_in_response = result.get('id')
            if work_item_id_in_response == work_item_id:
                print_result(True, f"UAT #{work_item_id} retrieved successfully")
                print(f"   📋 Title: {result.get('fields', {}).get('System.Title', 'N/A')}")
                print(f"   📊 State: {result.get('fields', {}).get('System.State', 'N/A')}")
                return True
            else:
                print_result(False, f"Work item ID mismatch: expected {work_item_id}, got {work_item_id_in_response}")
                print(f"   Response keys: {list(result.keys())}")
                return False
        else:
            print_result(False, f"Request failed with status {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"Exception occurred: {e}")
        return False

def test_list_uats():
    """Test 4: List UATs with filters"""
    print_test_header("List UAT Work Items")
    
    try:
        print(f"📤 Sending list request to {GATEWAY_UAT_URL}/list")
        response = requests.get(f"{GATEWAY_UAT_URL}/list?limit=10", timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            total = result.get('total', 0)
            uats = result.get('uats', [])
            print_result(True, f"Listed {total} UATs (showing {len(uats)})")
            
            if uats:
                print("   📋 Sample UATs:")
                for uat in uats[:3]:  # Show first 3
                    print(f"      - #{uat.get('id')}: {uat.get('title', 'N/A')[:60]}...")
            
            return True
        else:
            print_result(False, f"Request failed with status {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"Exception occurred: {e}")
        return False

def test_update_uat(work_item_id):
    """Test 5: Update UAT fields"""
    print_test_header("Update UAT Work Item")
    
    if not work_item_id:
        print_result(False, "No work_item_id provided (skipped)")
        return False
    
    try:
        updates = {
            "System.Description": "UPDATED: This UAT has been successfully updated by the Phase 7 integration test."
        }
        
        print(f"📤 Sending update request to {GATEWAY_UAT_URL}/{work_item_id}")
        response = requests.put(f"{GATEWAY_UAT_URL}/{work_item_id}", json=updates, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print_result(True, f"UAT #{work_item_id} updated successfully")
                print(f"   📝 Updated fields: {result.get('updated_fields', [])}")
                return True
            else:
                print_result(False, f"Update failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print_result(False, f"Request failed with status {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print_result(False, f"Exception occurred: {e}")
        return False

def run_all_tests():
    """Run all Phase 7 integration tests"""
    print("\n" + "="*80)
    print("🚀 PHASE 7 INTEGRATION TESTS - UAT MANAGEMENT SERVICE")
    print("="*80)
    print("Testing UAT CRUD operations through API Gateway")
    print(f"Base URL: {BASE_URL}")
    print(f"Gateway UAT Endpoint: {GATEWAY_UAT_URL}")
    print("="*80)
    
    results = {}
    
    # Test 1: Service Health
    results['health'] = test_service_health()
    
    # Test 2: Create UAT
    work_item_id = test_create_uat()
    results['create'] = work_item_id is not None
    
    # Test 3: Get UAT
    results['get'] = test_get_uat(work_item_id)
    
    # Test 4: List UATs
    results['list'] = test_list_uats()
    
    # Test 5: Update UAT
    results['update'] = test_update_uat(work_item_id)
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name.upper()}")
    
    print("="*80)
    print(f"Results: {passed}/{total} tests passed ({passed*100//total}%)")
    print("="*80)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Phase 7 is complete!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
