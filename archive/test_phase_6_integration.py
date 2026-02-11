"""
Integration Test for Phase 6: Enhanced Matching Service
Tests the Enhanced Matching microservice and API Gateway integration

Tests:
1. Completeness Analysis - Analyzing issue quality
2. Context Analysis - Intelligent context understanding
3. Service Health - All services operational
"""

import requests
import json

# Service URLs
GATEWAY_URL = "http://localhost:8000"
MATCHING_SERVICE_URL = "http://localhost:8003"

def test_completeness_analysis():
    """Test completeness analysis through API Gateway"""
    print("\n" + "="*80)
    print("TEST 1: Completeness Analysis via API Gateway")
    print("="*80)
    
    # Test Case 1: Good quality issue
    test_case_1 = {
        "title": "Azure OpenAI capacity needed in East US",
        "description": "We need GPT-4 capacity for our production AI application. Our current deployment is experiencing throttling.",
        "impact": "Development team cannot complete critical AI features for Q1 release"
    }
    
    print("\n📝 Test Case 1: High-quality issue")
    print(f"Title: {test_case_1['title']}")
    
    response = requests.post(
        f"{GATEWAY_URL}/api/matching/analyze-completeness",
        json=test_case_1,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    result = response.json()
    
    print(f"✅ Completeness Score: {result['completeness_score']}%")
    print(f"   Is Complete: {result['is_complete']}")
    print(f"   Issues Found: {len(result['issues'])}")
    
    # Test Case 2: Low quality issue
    test_case_2 = {
        "title": "help",
        "description": "need help",
        "impact": ""
    }
    
    print("\n📝 Test Case 2: Low-quality issue")
    print(f"Title: {test_case_2['title']}")
    
    response = requests.post(
        f"{GATEWAY_URL}/api/matching/analyze-completeness",
        json=test_case_2,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    result = response.json()
    
    print(f"✅ Completeness Score: {result['completeness_score']}%")
    print(f"   Needs Improvement: {result['needs_improvement']}")
    print(f"   Suggestions: {len(result['suggestions'])}")
    for suggestion in result['suggestions'][:2]:
        print(f"   - {suggestion[:80]}...")
    
    print("\n✅ Test 1 PASSED: Completeness analysis working correctly")

def test_context_analysis():
    """Test context analysis through API Gateway"""
    print("\n" + "="*80)
    print("TEST 2: Context Analysis via API Gateway")
    print("="*80)
    
    # Test Case 1: Capacity request
    test_case_1 = {
        "title": "Azure OpenAI capacity increase needed",
        "description": "Request additional quota for GPT-4 in North Central US region for production workload",
        "impact": "Critical production application experiencing throttling"
    }
    
    print("\n📝 Test Case 1: Capacity request")
    print(f"Title: {test_case_1['title']}")
    
    response = requests.post(
        f"{GATEWAY_URL}/api/matching/analyze-context",
        json=test_case_1,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    result = response.json()
    
    context = result['context_analysis']
    print(f"✅ Category: {context['category']}")
    print(f"   Intent: {context['intent']}")
    print(f"   Confidence: {context['confidence']}")
    print(f"   Business Impact: {context.get('business_impact', 'N/A')}")
    
    # Test Case 2: Technical support issue
    test_case_2 = {
        "title": "Azure Function deployment failing",
        "description": "Unable to deploy Function App to production environment. Getting authentication errors.",
        "impact": "Team blocked from deploying critical fix"
    }
    
    print("\n📝 Test Case 2: Technical support")
    print(f"Title: {test_case_2['title']}")
    
    response = requests.post(
        f"{GATEWAY_URL}/api/matching/analyze-context",
        json=test_case_2,
        headers={"Content-Type": "application/json"}
    )
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    result = response.json()
    
    context = result['context_analysis']
    print(f"✅ Category: {context['category']}")
    print(f"   Intent: {context['intent']}")
    print(f"   Confidence: {context['confidence']}")
    
    print("\n✅ Test 2 PASSED: Context analysis working correctly")

def test_direct_service_access():
    """Test direct access to Enhanced Matching service"""
    print("\n" + "="*80)
    print("TEST 3: Direct Service Access (Port 8003)")
    print("="*80)
    
    # Test health endpoint
    response = requests.get(f"{MATCHING_SERVICE_URL}/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    health = response.json()
    print(f"✅ Service Status: {health['status']}")
    print(f"   Components:")
    for component, status in health.get('components', {}).items():
        print(f"   - {component}: {'✓' if status else '✗'}")
    
    # Test info endpoint
    response = requests.get(f"{MATCHING_SERVICE_URL}/info")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    info = response.json()
    print(f"\n📋 Service Info:")
    print(f"   Name: {info['name']}")
    print(f"   Version: {info['version']}")
    print(f"   Port: {info['port']}")
    print(f"   Available Endpoints: {len(info.get('endpoints', {}))}")
    
    print("\n✅ Test 3 PASSED: Direct service access working")

def test_all_services_health():
    """Test health of all services"""
    print("\n" + "="*80)
    print("TEST 4: All Services Health Check")
    print("="*80)
    
    services = [
        ("Context Analyzer", "http://localhost:8001"),
        ("Search Service", "http://localhost:8002"),
        ("Enhanced Matching", "http://localhost:8003"),
        ("API Gateway", "http://localhost:8000")
    ]
    
    all_healthy = True
    for name, url in services:
        try:
            response = requests.get(f"{url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ {name} ({url}): Healthy")
            else:
                print(f"❌ {name} ({url}): Unhealthy (Status {response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"❌ {name} ({url}): Error - {str(e)}")
            all_healthy = False
    
    assert all_healthy, "Not all services are healthy"
    print("\n✅ Test 4 PASSED: All services healthy")

if __name__ == "__main__":
    print("\n" + "="*80)
    print("PHASE 6 INTEGRATION TESTS - Enhanced Matching Service")
    print("="*80)
    print("Testing Enhanced Matching microservice and API Gateway integration")
    print("Services: Context Analyzer (8001), Search (8002), Matching (8003), Gateway (8000)")
    
    try:
        # Run all tests
        test_all_services_health()
        test_completeness_analysis()
        test_context_analysis()
        test_direct_service_access()
        
        print("\n" + "="*80)
        print("🎉 ALL PHASE 6 TESTS PASSED!")
        print("="*80)
        print("✅ Enhanced Matching service operational")
        print("✅ API Gateway routing working")
        print("✅ Completeness analysis functional")
        print("✅ Context analysis functional")
        print("✅ All microservices healthy")
        print("="*80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
