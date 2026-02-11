"""
Phase 4 Integration Test
Tests the complete microservices architecture:
- API Gateway (port 8000) → Context Analyzer (port 8001)
"""

import requests
import json
from datetime import datetime

# Test data
test_cases = [
    {
        "name": "Azure SQL Connection Timeout",
        "data": {
            "title": "Azure SQL Database experiencing connection timeouts",
            "description": "Multiple customers reporting intermittent connection failures to Azure SQL Database in East US region. Errors indicate TCP timeout after 30 seconds.",
            "impact": "Critical - Production databases unavailable for 50+ customers"
        }
    },
    {
        "name": "Teams Meeting Recording",
        "data": {
            "title": "Teams meeting recordings not saving",
            "description": "Enterprise customers report that Teams meeting recordings are failing to save to OneDrive/SharePoint after meetings end.",
            "impact": "High - Compliance requirements for recording retention"
        }
    },
    {
        "name": "Azure AD B2C Authentication",
        "data": {
            "title": "Azure AD B2C login failures",
            "description": "Consumer-facing application experiencing 403 errors during Azure AD B2C authentication flow. Multi-factor authentication failing.",
            "impact": "Medium - Customer login blocked, alternative auth working"
        }
    }
]

def test_gateway_health():
    """Test API Gateway health endpoint"""
    print("\n" + "="*80)
    print("Testing API Gateway Health")
    print("="*80)
    
    response = requests.get("http://localhost:8000/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200, "Gateway health check failed"
    print("✅ Gateway is healthy")

def test_context_analyzer_health():
    """Test Context Analyzer health endpoint"""
    print("\n" + "="*80)
    print("Testing Context Analyzer Health")
    print("="*80)
    
    response = requests.get("http://localhost:8001/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200, "Context Analyzer health check failed"
    print("✅ Context Analyzer is healthy")

def test_direct_analysis():
    """Test Context Analyzer directly (bypassing gateway)"""
    print("\n" + "="*80)
    print("Testing Direct Analysis (Context Analyzer)")
    print("="*80)
    
    test_case = test_cases[0]
    print(f"\nTest Case: {test_case['name']}")
    
    response = requests.post(
        "http://localhost:8001/analyze",
        json=test_case['data'],
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    result = response.json()
    
    print(f"\nAnalysis ID: {result['analysis_id']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Primary Category: {result['primary_category']}")
    print(f"Key Concepts: {', '.join(result['key_concepts'][:5])}")
    
    assert response.status_code == 200, "Direct analysis failed"
    assert 'analysis_id' in result, "Missing analysis_id"
    print("✅ Direct analysis succeeded")

def test_gateway_routing():
    """Test complete pipeline: Gateway → Context Analyzer"""
    print("\n" + "="*80)
    print("Testing Complete Pipeline (Gateway → Context Analyzer)")
    print("="*80)
    
    for test_case in test_cases:
        print(f"\n{'='*80}")
        print(f"Test Case: {test_case['name']}")
        print('='*80)
        
        response = requests.post(
            "http://localhost:8000/api/analyze",
            json=test_case['data'],
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n📊 Analysis Results:")
            print(f"   Analysis ID: {result['analysis_id']}")
            print(f"   Timestamp: {result['timestamp']}")
            print(f"   Confidence: {result['confidence']}")
            print(f"   Primary Category: {result['primary_category']}")
            print(f"   Key Concepts: {', '.join(result['key_concepts'][:5])}")
            
            if result.get('detected_products'):
                print(f"   Detected Products: {', '.join(result['detected_products'])}")
            
            if result.get('detected_services'):
                print(f"   Detected Services: {', '.join(result['detected_services'])}")
            
            # Show reasoning summary
            reasoning = result.get('reasoning', {})
            if 'step_by_step' in reasoning:
                steps = reasoning['step_by_step']
                print(f"\n🔍 Analysis Steps ({len(steps)} steps):")
                for step in steps[:5]:  # Show first 5 steps
                    print(f"   {step}")
            
            print("\n✅ Pipeline test passed")
        else:
            print(f"❌ Pipeline test failed: {response.text}")
            raise AssertionError("Pipeline routing failed")

def main():
    print("\n" + "="*80)
    print("PHASE 4 INTEGRATION TEST")
    print("Testing Microservices Architecture")
    print("="*80)
    print(f"Test Time: {datetime.now().isoformat()}")
    print(f"Total Test Cases: {len(test_cases)}")
    
    try:
        # Test individual services
        test_gateway_health()
        test_context_analyzer_health()
        test_direct_analysis()
        
        # Test complete pipeline
        test_gateway_routing()
        
        print("\n" + "="*80)
        print("🎉 ALL TESTS PASSED!")
        print("="*80)
        print("\n✅ Phase 4 Integration Verified:")
        print("   - API Gateway operational on port 8000")
        print("   - Context Analyzer operational on port 8001")
        print("   - Gateway successfully routes to Context Analyzer")
        print("   - Analysis results returned correctly")
        print("   - Microservices architecture working as designed")
        
    except Exception as e:
        print("\n" + "="*80)
        print("❌ TESTS FAILED!")
        print("="*80)
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()
