"""
Phase 8: LLM Classifier Microservice Integration Tests
Tests the LLM Classifier service standalone and through API Gateway
"""

import requests
import time
import sys

# Service URLs
CLASSIFIER_SERVICE_URL = "http://localhost:8005"
GATEWAY_URL = "http://localhost:8000"

def test_service_health():
    """Test 1: Service health check"""
    print("\n" + "="*80)
    print("Test 1: Service Health Check")
    print("="*80)
    
    try:
        response = requests.get(f"{CLASSIFIER_SERVICE_URL}/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["status"] == "healthy", "Service not healthy"
        assert data["service"] == "llm-classifier", "Unexpected service name"
        
        print("✅ Service health check passed")
        print(f"   Status: {data['status']}")
        print(f"   Service: {data['service']}")
        print(f"   Version: {data.get('version', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"❌ Service health check failed: {e}")
        return False

def test_service_info():
    """Test 2: Service information"""
    print("\n" + "="*80)
    print("Test 2: Service Information")
    print("="*80)
    
    try:
        response = requests.get(f"{CLASSIFIER_SERVICE_URL}/info", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "endpoints" in data, "Missing endpoints information"
        
        print("✅ Service info retrieved successfully")
        print(f"   Service: {data['service']}")
        print(f"   Description: {data['description']}")
        print(f"   Model: {data.get('model', 'N/A')}")
        print(f"   Deployment: {data.get('deployment', 'N/A')}")
        print(f"   Available endpoints: {len(data['endpoints'])}")
        return True
        
    except Exception as e:
        print(f"❌ Service info check failed: {e}")
        return False

def test_technical_support_classification():
    """Test 3: Technical support classification (SCVMM migration)"""
    print("\n" + "="*80)
    print("Test 3: Technical Support Classification")
    print("="*80)
    
    try:
        payload = {
            "title": "SCVMM Migration to Azure",
            "description": "Customer needs help migrating System Center Virtual Machine Manager to Azure. Looking for migration tools and guidance.",
            "impact": "high"
        }
        
        response = requests.post(
            f"{CLASSIFIER_SERVICE_URL}/classify",
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        result = response.json()
        print("✅ Classification successful")
        print(f"   Category: {result['category']}")
        print(f"   Intent: {result['intent']}")
        print(f"   Business Impact: {result['business_impact']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Reasoning: {result['reasoning'][:100]}...")
        
        # Validate expected classification
        assert result['category'] in ['technical_support', 'migration_modernization'], \
            f"Unexpected category: {result['category']}"
        assert result['confidence'] > 0.6, f"Low confidence: {result['confidence']}"
        
        return True
        
    except Exception as e:
        print(f"❌ Technical support classification failed: {e}")
        return False

def test_service_availability_classification():
    """Test 4: Service availability classification (SQL MI regional availability)"""
    print("\n" + "="*80)
    print("Test 4: Service Availability Classification")
    print("="*80)
    
    try:
        payload = {
            "title": "SQL Managed Instance in West Europe",
            "description": "Is SQL Managed Instance available in the West Europe region? Need to deploy for EU data residency requirements.",
            "impact": "medium"
        }
        
        response = requests.post(
            f"{CLASSIFIER_SERVICE_URL}/classify",
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        result = response.json()
        print("✅ Classification successful")
        print(f"   Category: {result['category']}")
        print(f"   Intent: {result['intent']}")
        print(f"   Business Impact: {result['business_impact']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Reasoning: {result['reasoning'][:100]}...")
        
        # Validate expected classification
        assert result['category'] in ['service_availability', 'data_sovereignty'], \
            f"Unexpected category: {result['category']}"
        assert result['confidence'] > 0.6, f"Low confidence: {result['confidence']}"
        
        return True
        
    except Exception as e:
        print(f"❌ Service availability classification failed: {e}")
        return False

def test_seeking_guidance_classification():
    """Test 5: Seeking guidance classification (Planner demo)"""
    print("\n" + "="*80)
    print("Test 5: Seeking Guidance Classification")
    print("="*80)
    
    try:
        payload = {
            "title": "Microsoft Planner Demo",
            "description": "Can you provide a demo of Microsoft Planner for our team? We want to understand how to use it for project management.",
            "impact": "low"
        }
        
        response = requests.post(
            f"{CLASSIFIER_SERVICE_URL}/classify",
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        result = response.json()
        print("✅ Classification successful")
        print(f"   Category: {result['category']}")
        print(f"   Intent: {result['intent']}")
        print(f"   Business Impact: {result['business_impact']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Reasoning: {result['reasoning'][:100]}...")
        
        # Validate expected classification
        assert result['intent'] in ['seeking_guidance', 'best_practices'], \
            f"Unexpected intent: {result['intent']}"
        assert result['confidence'] > 0.5, f"Low confidence: {result['confidence']}"
        
        return True
        
    except Exception as e:
        print(f"❌ Seeking guidance classification failed: {e}")
        return False

def test_batch_classification():
    """Test 6: Batch classification"""
    print("\n" + "="*80)
    print("Test 6: Batch Classification")
    print("="*80)
    
    try:
        items = [
            {
                "title": "Azure AD B2C Setup",
                "description": "Need help setting up Azure AD B2C for customer authentication",
                "impact": "high"
            },
            {
                "title": "Cost Optimization",
                "description": "Our Azure costs are increasing. Need recommendations for cost optimization.",
                "impact": "medium"
            },
            {
                "title": "Compliance Requirements",
                "description": "What are the compliance certifications for Azure in EU regions?",
                "impact": "critical"
            }
        ]
        
        payload = {
            "items": items,
            "use_cache": True
        }
        
        response = requests.post(
            f"{CLASSIFIER_SERVICE_URL}/classify/batch",
            json=payload,
            timeout=120
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        result = response.json()
        print("✅ Batch classification successful")
        print(f"   Total items: {result['total']}")
        print(f"   Successful: {result['successful']}")
        print(f"   Failed: {result['failed']}")
        
        # Validate batch results
        assert result['total'] == len(items), "Incorrect total count"
        assert len(result['results']) == len(items), "Missing results"
        
        for i, classification in enumerate(result['results']):
            print(f"\n   Item {i+1}:")
            print(f"      Category: {classification['category']}")
            print(f"      Intent: {classification['intent']}")
            print(f"      Confidence: {classification['confidence']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Batch classification failed: {e}")
        return False

def test_gateway_classification():
    """Test 7: Classification through API Gateway"""
    print("\n" + "="*80)
    print("Test 7: Classification Through API Gateway")
    print("="*80)
    
    try:
        payload = {
            "title": "Feature Request: Dark Mode",
            "description": "Please add dark mode support to the Azure Portal. This would greatly improve user experience.",
            "impact": "medium"
        }
        
        response = requests.post(
            f"{GATEWAY_URL}/api/classify/classify",
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        result = response.json()
        print("✅ Gateway classification successful")
        print(f"   Category: {result['category']}")
        print(f"   Intent: {result['intent']}")
        print(f"   Business Impact: {result['business_impact']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        
        # Validate feature request classification
        assert result['category'] == 'feature_request', \
            f"Expected 'feature_request', got '{result['category']}'"
        assert result['intent'] == 'requesting_feature', \
            f"Expected 'requesting_feature', got '{result['intent']}'"
        
        return True
        
    except Exception as e:
        print(f"❌ Gateway classification failed: {e}")
        return False

def test_cache_functionality():
    """Test 8: Cache functionality"""
    print("\n" + "="*80)
    print("Test 8: Cache Functionality")
    print("="*80)
    
    try:
        # Get initial cache stats
        response = requests.get(f"{CLASSIFIER_SERVICE_URL}/cache/stats", timeout=10)
        assert response.status_code == 200, "Failed to get cache stats"
        
        initial_stats = response.json()
        print("✅ Cache statistics retrieved")
        print(f"   Initial stats: {initial_stats}")
        
        # Make a classification request
        payload = {
            "title": "Test Cache",
            "description": "Testing cache functionality with repeated requests",
            "impact": "low"
        }
        
        # First request (should cache)
        response1 = requests.post(
            f"{CLASSIFIER_SERVICE_URL}/classify",
            json=payload,
            timeout=60
        )
        assert response1.status_code == 200, "First classification failed"
        
        # Second request (should hit cache)
        response2 = requests.post(
            f"{CLASSIFIER_SERVICE_URL}/classify",
            json=payload,
            timeout=60
        )
        assert response2.status_code == 200, "Second classification failed"
        
        # Results should be identical
        result1 = response1.json()
        result2 = response2.json()
        assert result1['category'] == result2['category'], "Results don't match"
        assert result1['confidence'] == result2['confidence'], "Confidence doesn't match"
        
        print("✅ Cache working correctly")
        print(f"   Both requests returned identical results")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache functionality test failed: {e}")
        return False

def test_all_services_health():
    """Test 9: All services health check"""
    print("\n" + "="*80)
    print("Test 9: All Services Health Check (6 Services)")
    print("="*80)
    
    services = [
        ("Context Analyzer", "http://localhost:8001/health"),
        ("Search Service", "http://localhost:8002/health"),
        ("Enhanced Matching", "http://localhost:8003/health"),
        ("UAT Management", "http://localhost:8004/health"),
        ("LLM Classifier", "http://localhost:8005/health"),
        ("API Gateway", "http://localhost:8000/health"),
    ]
    
    all_healthy = True
    
    for service_name, url in services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"   ✅ {service_name}: Healthy")
            else:
                print(f"   ❌ {service_name}: Unhealthy (Status {response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"   ❌ {service_name}: Unreachable ({str(e)[:50]})")
            all_healthy = False
    
    if all_healthy:
        print("\n✅ All 6 services are healthy!")
    else:
        print("\n❌ Some services are not healthy")
    
    return all_healthy

def run_all_tests():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("🧪 PHASE 8: LLM CLASSIFIER MICROSERVICE INTEGRATION TESTS")
    print("="*80)
    print("Testing the LLM Classifier service and integration with API Gateway")
    print("Expected: 6 services running (Context, Search, Matching, UAT, Classifier, Gateway)")
    
    tests = [
        ("Service Health Check", test_service_health),
        ("Service Information", test_service_info),
        ("Technical Support Classification", test_technical_support_classification),
        ("Service Availability Classification", test_service_availability_classification),
        ("Seeking Guidance Classification", test_seeking_guidance_classification),
        ("Batch Classification", test_batch_classification),
        ("Gateway Classification", test_gateway_classification),
        ("Cache Functionality", test_cache_functionality),
        ("All Services Health", test_all_services_health),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"⚠️  {test_name} did not pass all assertions")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} raised an exception: {e}")
        
        time.sleep(1)  # Brief pause between tests
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Success Rate: {(passed/len(tests)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! Phase 8 is complete!")
        print("\n✨ LLM Classifier service is operational with:")
        print("   - GPT-4 powered classification")
        print("   - 20 categories, 15 intents, 4 business impact levels")
        print("   - Smart caching with API-first strategy")
        print("   - Batch processing support")
        print("   - Full API Gateway integration")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
