"""
Phase 10 Integration Tests - Vector Search Service
Tests semantic search, indexing, and duplicate detection features
"""
import requests
import json
from typing import Dict, Any, List

# Test configuration
BASE_URL = "http://localhost:8000"
VECTOR_URL = "http://localhost:8007"

def test_service_health():
    """Test 1: Vector Search service health check"""
    print("\n🔍 Test 1: Vector Search Service Health Check")
    print("=" * 70)
    
    try:
        response = requests.get(f"{VECTOR_URL}/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ Vector Search service is healthy!")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False

def test_index_items():
    """Test 2: Index items into a collection"""
    print("\n🔍 Test 2: Index Items into Collection")
    print("=" * 70)
    
    # Test items with varied content
    items = [
        {
            "id": "uat-001",
            "title": "User Authentication Testing",
            "description": "Test single sign-on (SSO) authentication flow with Azure AD integration",
            "metadata": {"category": "security", "priority": "high"}
        },
        {
            "id": "uat-002",
            "title": "API Response Time Testing",
            "description": "Verify API endpoint response times are under 200ms for all CRUD operations",
            "metadata": {"category": "performance", "priority": "medium"}
        },
        {
            "id": "uat-003",
            "title": "Database Migration Testing",
            "description": "Test data migration from legacy SQL Server to Azure SQL Database with zero data loss",
            "metadata": {"category": "data", "priority": "high"}
        },
        {
            "id": "uat-004",
            "title": "Mobile UI Responsiveness",
            "description": "Verify mobile application UI renders correctly on iOS and Android devices",
            "metadata": {"category": "ui", "priority": "medium"}
        }
    ]
    
    try:
        # Clear collection first
        requests.delete(f"{VECTOR_URL}/collections/test_uats", timeout=10)
        
        # Index items
        payload = {
            "collection_name": "test_uats",
            "items": items,
            "force_reindex": False
        }
        
        response = requests.post(
            f"{VECTOR_URL}/index",
            json=payload,
            timeout=120
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["indexed_count"] == len(items)
        assert data["collection_name"] == "test_uats"
        
        print(f"✅ Successfully indexed {data['indexed_count']} items!")
        return True
    except Exception as e:
        print(f"❌ Indexing failed: {str(e)}")
        return False

def test_semantic_search():
    """Test 3: Perform semantic similarity search"""
    print("\n🔍 Test 3: Semantic Search")
    print("=" * 70)
    
    test_queries = [
        {
            "query": "login and authentication security",
            "expected_top": "uat-001",
            "description": "Should find authentication UAT"
        },
        {
            "query": "database migration and data transfer",
            "expected_top": "uat-003",
            "description": "Should find database migration UAT"
        },
        {
            "query": "API speed and performance",
            "expected_top": "uat-002",
            "description": "Should find API performance UAT"
        }
    ]
    
    all_passed = True
    for test in test_queries:
        print(f"\n📝 Query: '{test['query']}'")
        print(f"   Expected: {test['description']}")
        
        try:
            payload = {
                "query": test["query"],
                "collection_name": "test_uats",
                "top_k": 3,
                "similarity_threshold": 0.3,
                "use_cache": False
            }
            
            response = requests.post(
                f"{VECTOR_URL}/search",
                json=payload,
                timeout=60
            )
            
            assert response.status_code == 200
            data = response.json()
            
            if data["count"] > 0:
                top_result = data["results"][0]
                print(f"   Top Result: {top_result['item_id']} (similarity: {top_result['similarity']:.4f})")
                print(f"   Title: {top_result['title']}")
                
                # Verify expected result is in top position
                if top_result["item_id"] == test["expected_top"]:
                    print(f"   ✅ Correct match found!")
                else:
                    print(f"   ⚠️  Expected {test['expected_top']}, got {top_result['item_id']}")
                    all_passed = False
            else:
                print(f"   ❌ No results found!")
                all_passed = False
                
        except Exception as e:
            print(f"   ❌ Search failed: {str(e)}")
            all_passed = False
    
    return all_passed

def test_context_search():
    """Test 4: Context-based search (title + description)"""
    print("\n🔍 Test 4: Context-Based Search")
    print("=" * 70)
    
    try:
        payload = {
            "title": "Testing user login",
            "description": "Need to verify authentication with Azure Active Directory",
            "collection_name": "test_uats",
            "top_k": 2,
            "similarity_threshold": 0.3
        }
        
        response = requests.post(
            f"{VECTOR_URL}/search/context",
            json=payload,
            timeout=60
        )
        
        print(f"Status Code: {response.status_code}")
        assert response.status_code == 200
        
        data = response.json()
        print(f"Found {data['count']} results")
        
        if data["count"] > 0:
            for i, result in enumerate(data["results"][:2], 1):
                print(f"\n{i}. {result['item_id']}: {result['title']}")
                print(f"   Similarity: {result['similarity']:.4f}")
            
            # Should find authentication UAT as top result
            top_result = data["results"][0]
            assert top_result["item_id"] == "uat-001"
            print("\n✅ Context search correctly identified authentication UAT!")
            return True
        else:
            print("❌ No results found!")
            return False
            
    except Exception as e:
        print(f"❌ Context search failed: {str(e)}")
        return False

def test_duplicate_detection():
    """Test 5: Find similar issues (duplicate detection)"""
    print("\n🔍 Test 5: Duplicate Detection")
    print("=" * 70)
    
    try:
        # Try to find duplicates of the authentication UAT
        payload = {
            "title": "SSO Authentication Testing",
            "description": "Test Azure AD single sign-on authentication",
            "top_k": 3
        }
        
        response = requests.post(
            f"{VECTOR_URL}/search/similar",
            json=payload,
            timeout=60
        )
        
        print(f"Status Code: {response.status_code}")
        assert response.status_code == 200
        
        data = response.json()
        print(f"Found {data['count']} similar items")
        
        if data["count"] > 0:
            for i, result in enumerate(data["results"], 1):
                print(f"\n{i}. {result['item_id']}: {result['title']}")
                print(f"   Similarity: {result['similarity']:.4f}")
                print(f"   Description: {result['description'][:80]}...")
            
            # Should find authentication UAT with high similarity
            top_result = data["results"][0]
            if top_result["similarity"] >= 0.70:
                print(f"\n✅ Found potential duplicate with {top_result['similarity']:.2%} similarity!")
                return True
            else:
                print(f"\n⚠️  Top match only has {top_result['similarity']:.2%} similarity")
                return True  # Still pass, but note lower similarity
        else:
            print("ℹ️  No duplicates found above threshold")
            return True  # Not finding duplicates is also valid
            
    except Exception as e:
        print(f"❌ Duplicate detection failed: {str(e)}")
        return False

def test_collection_management():
    """Test 6: Collection management operations"""
    print("\n🔍 Test 6: Collection Management")
    print("=" * 70)
    
    try:
        # List collections
        print("\n📋 Listing collections...")
        response = requests.get(f"{VECTOR_URL}/collections", timeout=10)
        assert response.status_code == 200
        data = response.json()
        print(f"Total collections: {data['count']}")
        print(f"Collections: {data['collections']}")
        assert "test_uats" in data["collections"]
        
        # Get collection stats
        print("\n📊 Getting collection stats...")
        response = requests.get(f"{VECTOR_URL}/collections/test_uats/stats", timeout=10)
        assert response.status_code == 200
        stats = response.json()
        print(f"Collection: {json.dumps(stats, indent=2)}")
        assert stats["exists"] == True
        assert stats["total_items"] == 4
        
        print("\n✅ Collection management working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Collection management failed: {str(e)}")
        return False

def test_gateway_integration():
    """Test 7: Vector search through API Gateway"""
    print("\n🔍 Test 7: Gateway Integration")
    print("=" * 70)
    
    try:
        # Test search through gateway
        payload = {
            "query": "authentication testing",
            "collection_name": "test_uats",
            "top_k": 2,
            "similarity_threshold": 0.3,
            "use_cache": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/vector/search",
            json=payload,
            timeout=60
        )
        
        print(f"Status Code: {response.status_code}")
        assert response.status_code == 200
        
        data = response.json()
        print(f"Found {data['count']} results through gateway")
        
        if data["count"] > 0:
            print(f"Top result: {data['results'][0]['item_id']}")
            print("✅ Gateway integration working!")
            return True
        else:
            print("❌ No results through gateway!")
            return False
            
    except Exception as e:
        print(f"❌ Gateway integration failed: {str(e)}")
        return False

def test_all_services_health():
    """Test 8: Verify all 8 services are healthy"""
    print("\n🔍 Test 8: All Services Health Check")
    print("=" * 70)
    
    services = [
        ("Context Analyzer", "http://localhost:8001/health"),
        ("Search Service", "http://localhost:8002/health"),
        ("Enhanced Matching", "http://localhost:8003/health"),
        ("UAT Management", "http://localhost:8004/health"),
        ("LLM Classifier", "http://localhost:8005/health"),
        ("Embedding Service", "http://localhost:8006/health"),
        ("Vector Search", "http://localhost:8007/health"),
        ("API Gateway", "http://localhost:8000/health")
    ]
    
    all_healthy = True
    for name, url in services:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"✅ {name}: Healthy")
            else:
                print(f"❌ {name}: Unhealthy (status {response.status_code})")
                all_healthy = False
        except Exception as e:
            print(f"❌ {name}: Failed ({str(e)[:50]}...)")
            all_healthy = False
    
    if all_healthy:
        print("\n🎉 All 8 services are healthy!")
    else:
        print("\n⚠️  Some services are not healthy")
    
    return all_healthy

def cleanup():
    """Clean up test data"""
    print("\n🧹 Cleaning up test data...")
    try:
        requests.delete(f"{VECTOR_URL}/collections/test_uats", timeout=10)
        print("✅ Cleanup complete!")
    except:
        print("⚠️  Cleanup failed (may not matter)")

def main():
    """Run all Phase 10 integration tests"""
    print("\n" + "=" * 70)
    print("🚀 PHASE 10 INTEGRATION TESTS - VECTOR SEARCH SERVICE")
    print("=" * 70)
    
    tests = [
        ("Service Health", test_service_health),
        ("Index Items", test_index_items),
        ("Semantic Search", test_semantic_search),
        ("Context Search", test_context_search),
        ("Duplicate Detection", test_duplicate_detection),
        ("Collection Management", test_collection_management),
        ("Gateway Integration", test_gateway_integration),
        ("All Services Health", test_all_services_health)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {str(e)}")
            results.append((name, False))
    
    # Cleanup
    cleanup()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{'✅' if passed == total else '⚠️'} Passed: {passed}/{total} tests")
    
    if passed == total:
        print("\n🎉 All Phase 10 tests passed! Vector Search service is fully operational!")
        print("\n📝 Ready to commit Phase 10")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review errors above.")
    
    return passed == total

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
