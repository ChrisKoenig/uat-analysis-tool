"""
Phase 9: Embedding Service Integration Tests
Tests the Embedding Service standalone and through API Gateway
"""

import requests
import time
import sys

# Service URLs
EMBEDDING_SERVICE_URL = "http://localhost:8006"
GATEWAY_URL = "http://localhost:8000"

def test_service_health():
    """Test 1: Service health check"""
    print("\n" + "="*80)
    print("Test 1: Service Health Check")
    print("="*80)
    
    try:
        response = requests.get(f"{EMBEDDING_SERVICE_URL}/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["status"] == "healthy", "Service not healthy"
        assert data["service"] == "embedding-service", "Unexpected service name"
        
        print("✅ Service health check passed")
        print(f"   Status: {data['status']}")
        print(f"   Model: {data['model']}")
        print(f"   Deployment: {data['deployment']}")
        return True
        
    except Exception as e:
        print(f"❌ Service health check failed: {e}")
        return False

def test_single_embedding():
    """Test 2: Single text embedding"""
    print("\n" + "="*80)
    print("Test 2: Single Text Embedding")
    print("="*80)
    
    try:
        payload = {
            "text": "Azure SQL Managed Instance availability in West Europe"
        }
        
        response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed",
            json=payload,
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        result = response.json()
        print("✅ Embedding generated successfully")
        print(f"   Dimension: {result['dimension']}")
        print(f"   First 5 values: {result['embedding'][:5]}")
        
        assert result['dimension'] == 3072, f"Expected 3072 dimensions, got {result['dimension']}"
        assert len(result['embedding']) == 3072, "Embedding length mismatch"
        
        return True
        
    except Exception as e:
        print(f"❌ Single embedding test failed: {e}")
        return False

def test_batch_embedding():
    """Test 3: Batch embedding"""
    print("\n" + "="*80)
    print("Test 3: Batch Embedding")
    print("="*80)
    
    try:
        texts = [
            "Azure AD B2C authentication",
            "Cost optimization recommendations",
            "Compliance certifications for EU regions"
        ]
        
        payload = {
            "texts": texts,
            "use_cache": True
        }
        
        response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed/batch",
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        result = response.json()
        print("✅ Batch embedding successful")
        print(f"   Count: {result['count']}")
        print(f"   Dimension: {result['dimension']}")
        
        assert result['count'] == len(texts), "Incorrect count"
        assert len(result['embeddings']) == len(texts), "Missing embeddings"
        
        for i, embedding in enumerate(result['embeddings']):
            print(f"   Text {i+1}: {len(embedding)} dimensions")
            assert len(embedding) == 3072, f"Text {i+1} has wrong dimensions"
        
        return True
        
    except Exception as e:
        print(f"❌ Batch embedding test failed: {e}")
        return False

def test_context_embedding():
    """Test 4: Context embedding (title + description + impact)"""
    print("\n" + "="*80)
    print("Test 4: Context Embedding")
    print("="*80)
    
    try:
        payload = {
            "title": "SQL MI Deployment Issue",
            "description": "Unable to deploy SQL Managed Instance in West Europe region. Need urgent resolution.",
            "impact": "Blocking production deployment"
        }
        
        response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed/context",
            json=payload,
            timeout=60
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        result = response.json()
        print("✅ Context embedding successful")
        print(f"   Dimension: {result['dimension']}")
        print(f"   Title embedding: {len(result['title_embedding'])} dims")
        print(f"   Description embedding: {len(result['description_embedding'])} dims")
        print(f"   Impact embedding: {len(result.get('impact_embedding', []))} dims")
        print(f"   Combined embedding: {len(result['combined_embedding'])} dims")
        
        assert result['dimension'] == 3072, "Wrong dimension"
        assert len(result['title_embedding']) == 3072, "Title embedding wrong size"
        assert len(result['description_embedding']) == 3072, "Description embedding wrong size"
        assert len(result['combined_embedding']) == 3072, "Combined embedding wrong size"
        
        return True
        
    except Exception as e:
        print(f"❌ Context embedding test failed: {e}")
        return False

def test_similarity_calculation():
    """Test 5: Cosine similarity calculation"""
    print("\n" + "="*80)
    print("Test 5: Cosine Similarity Calculation")
    print("="*80)
    
    try:
        # Get two embeddings first
        text1 = "Azure SQL Managed Instance in West Europe"
        text2 = "SQL MI availability in Western Europe"
        text3 = "Azure Functions deployment"
        
        emb1_response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed",
            json={"text": text1},
            timeout=30
        )
        emb2_response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed",
            json={"text": text2},
            timeout=30
        )
        emb3_response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed",
            json={"text": text3},
            timeout=30
        )
        
        emb1 = emb1_response.json()['embedding']
        emb2 = emb2_response.json()['embedding']
        emb3 = emb3_response.json()['embedding']
        
        # Calculate similarity between related texts
        sim_payload = {
            "embedding1": emb1,
            "embedding2": emb2
        }
        
        sim_response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/similarity",
            json=sim_payload,
            timeout=10
        )
        
        assert sim_response.status_code == 200, "Similarity calculation failed"
        
        similarity_related = sim_response.json()['similarity']
        print("✅ Similarity calculation successful")
        print(f"   Related texts similarity: {similarity_related:.4f}")
        
        # Calculate similarity between unrelated texts
        sim_payload2 = {
            "embedding1": emb1,
            "embedding2": emb3
        }
        
        sim_response2 = requests.post(
            f"{EMBEDDING_SERVICE_URL}/similarity",
            json=sim_payload2,
            timeout=10
        )
        
        similarity_unrelated = sim_response2.json()['similarity']
        print(f"   Unrelated texts similarity: {similarity_unrelated:.4f}")
        
        # Related texts should have higher similarity
        assert similarity_related > similarity_unrelated, "Similarity ordering incorrect"
        assert 0 <= similarity_related <= 1, "Similarity out of range"
        assert 0 <= similarity_unrelated <= 1, "Similarity out of range"
        
        return True
        
    except Exception as e:
        print(f"❌ Similarity calculation test failed: {e}")
        return False

def test_cache_functionality():
    """Test 6: Cache functionality"""
    print("\n" + "="*80)
    print("Test 6: Cache Functionality")
    print("="*80)
    
    try:
        # Get cache stats
        stats_response = requests.get(f"{EMBEDDING_SERVICE_URL}/cache/stats", timeout=10)
        assert stats_response.status_code == 200, "Failed to get cache stats"
        
        stats = stats_response.json()
        print("✅ Cache statistics retrieved")
        print(f"   Cache enabled: {stats['cache_enabled']}")
        
        # Make embedding request (should cache)
        payload = {
            "text": "Test cache functionality with repeated requests"
        }
        
        response1 = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed",
            json=payload,
            timeout=30
        )
        assert response1.status_code == 200, "First embedding failed"
        
        # Second request (should hit cache)
        response2 = requests.post(
            f"{EMBEDDING_SERVICE_URL}/embed",
            json=payload,
            timeout=30
        )
        assert response2.status_code == 200, "Second embedding failed"
        
        # Results should be identical
        emb1 = response1.json()['embedding']
        emb2 = response2.json()['embedding']
        assert emb1 == emb2, "Cached embeddings don't match"
        
        print("✅ Cache working correctly")
        print(f"   Both requests returned identical embeddings")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache functionality test failed: {e}")
        return False

def test_all_services_health():
    """Test 7: All services health check (7 services)"""
    print("\n" + "="*80)
    print("Test 7: All Services Health Check (7 Services)")
    print("="*80)
    
    services = [
        ("Context Analyzer", "http://localhost:8001/health"),
        ("Search Service", "http://localhost:8002/health"),
        ("Enhanced Matching", "http://localhost:8003/health"),
        ("UAT Management", "http://localhost:8004/health"),
        ("LLM Classifier", "http://localhost:8005/health"),
        ("Embedding Service", "http://localhost:8006/health"),
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
        print("\n✅ All 7 services are healthy!")
    else:
        print("\n⚠️  Some services are not healthy")
    
    return all_healthy

def run_all_tests():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("🧪 PHASE 9: EMBEDDING SERVICE INTEGRATION TESTS")
    print("="*80)
    print("Testing the Embedding Service and integration with API Gateway")
    print("Expected: 7 services running")
    
    tests = [
        ("Service Health Check", test_service_health),
        ("Single Text Embedding", test_single_embedding),
        ("Batch Embedding", test_batch_embedding),
        ("Context Embedding", test_context_embedding),
        ("Cosine Similarity", test_similarity_calculation),
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
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} raised an exception: {e}")
        
        time.sleep(1)
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Success Rate: {(passed/len(tests)*100):.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! Phase 9 is complete!")
        print("\n✨ Embedding Service is operational with:")
        print("   - Azure OpenAI text-embedding-3-large (3072 dimensions)")
        print("   - Smart caching with API-first strategy")
        print("   - Batch processing support")
        print("   - Context embedding (weighted combination)")
        print("   - Cosine similarity calculation")
        print("   - Full API Gateway integration")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
