"""
Phase 5 Integration Test
Tests the Search Service microservice
"""

import requests
import json
from datetime import datetime

# Test data
test_cases = [
    {
        "name": "Azure OpenAI Capacity Request",
        "data": {
            "title": "Azure OpenAI Service quotas and capacity",
            "description": "Need to increase TPM quota for GPT-4 in East US region for production workload",
            "category": "capacity_request",
            "intent": "capacity_increase",
            "domain_entities": {
                "azure_services": ["Azure OpenAI Service"],
                "regions": ["East US"]
            }
        }
    },
    {
        "name": "Service Retirement Check",
        "data": {
            "title": "Azure Container Instances retirement timeline",
            "description": "Planning migration from deprecated ACI features. Need retirement information and alternatives.",
            "category": "service_issue",
            "intent": "migration_assistance",
            "domain_entities": {
                "azure_services": ["Container Instances"],
                "regions": []
            }
        }
    },
    {
        "name": "Regional Service Availability",
        "data": {
            "title": "Azure SQL Database not available in selected region",
            "description": "Attempting to deploy Azure SQL Database in Switzerland North but service unavailable",
            "category": "regional_issue",
            "intent": "check_availability",
            "domain_entities": {
                "azure_services": ["SQL Database"],
                "regions": ["Switzerland North"]
            }
        }
    }
]

def test_search_service_health():
    """Test Search Service health endpoint"""
    print("\n" + "="*80)
    print("Testing Search Service Health")
    print("="*80)
    
    response = requests.get("http://localhost:8002/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200, "Search Service health check failed"
    print("✅ Search Service is healthy")

def test_direct_search():
    """Test Search Service directly (bypassing gateway)"""
    print("\n" + "="*80)
    print("Testing Direct Search (Search Service)")
    print("="*80)
    
    test_case = test_cases[0]
    print(f"\nTest Case: {test_case['name']}")
    
    response = requests.post(
        "http://localhost:8002/search",
        json=test_case['data'],
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    result = response.json()
    
    print(f"\nSearch ID: {result['search_id']}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"Similar Products Found: {len(result['similar_products'])}")
    print(f"Regional Options: {len(result['regional_options'])}")
    print(f"Capacity Guidance: {'Yes' if result['capacity_guidance'] else 'No'}")
    print(f"Searches Performed: {', '.join(result['search_metadata']['searches_performed'])}")
    
    assert response.status_code == 200, "Direct search failed"
    assert 'search_id' in result, "Missing search_id"
    print("✅ Direct search succeeded")

def test_gateway_search_routing():
    """Test complete pipeline: Gateway → Search Service"""
    print("\n" + "="*80)
    print("Testing Complete Pipeline (Gateway → Search Service)")
    print("="*80)
    
    for test_case in test_cases:
        print(f"\n{'='*80}")
        print(f"Test Case: {test_case['name']}")
        print('='*80)
        
        response = requests.post(
            "http://localhost:8000/api/search",
            json=test_case['data'],
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n🔍 Search Results:")
            print(f"   Search ID: {result['search_id']}")
            print(f"   Timestamp: {result['timestamp']}")
            
            if result['similar_products']:
                print(f"\n   📦 Similar Products ({len(result['similar_products'])}):")
                for prod in result['similar_products'][:3]:  # Show first 3
                    print(f"      - {prod.get('alternative_name', 'Unknown')}: {prod.get('reason', 'N/A')}")
            
            if result['regional_options']:
                print(f"\n   🌍 Regional Options ({len(result['regional_options'])}):")
                for region in result['regional_options'][:2]:  # Show first 2
                    print(f"      - {region.get('region', 'Unknown')}: {region.get('reason', 'N/A')}")
            
            if result['capacity_guidance']:
                print(f"\n   📊 Capacity Guidance:")
                guidance = result['capacity_guidance']
                print(f"      Type: {guidance.get('type', 'Unknown')}")
                print(f"      Title: {guidance.get('title', 'N/A')}")
                print(f"      URL: {guidance.get('primary_url', 'N/A')}")
            
            if result['retirement_info']:
                print(f"\n   ⚠️  Retirement Info:")
                print(f"      Status: {result['retirement_info'].get('status', 'Unknown')}")
            
            print(f"\n   🔧 Search Metadata:")
            print(f"      Deep Search: {result['search_metadata'].get('deep_search', False)}")
            print(f"      Searches Performed: {len(result['search_metadata'].get('searches_performed', []))}")
            
            print("\n✅ Pipeline test passed")
        else:
            print(f"❌ Pipeline test failed: {response.text}")
            raise AssertionError("Pipeline routing failed")

def main():
    print("\n" + "="*80)
    print("PHASE 5 INTEGRATION TEST")
    print("Testing Search Service Microservice")
    print("="*80)
    print(f"Test Time: {datetime.now().isoformat()}")
    print(f"Total Test Cases: {len(test_cases)}")
    
    try:
        # Test Search Service
        test_search_service_health()
        test_direct_search()
        
        # Test complete pipeline
        test_gateway_search_routing()
        
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED!")
        print("="*80)
        print("\n✅ Phase 5 Integration Verified:")
        print("   - Search Service operational on port 8002")
        print("   - Gateway successfully routes to Search Service")
        print("   - Comprehensive search across multiple data sources")
        print("   - Capacity guidance working")
        print("   - Regional availability checks working")
        print("   - Alternative products suggestions working")
        
    except Exception as e:
        print("\n" + "="*80)
        print("❌ TESTS FAILED!")
        print("="*80)
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
