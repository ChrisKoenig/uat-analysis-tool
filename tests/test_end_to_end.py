"""
End-to-End Integration Tests - All 8 Microservices
Tests complete user workflows across the entire system
"""
import requests
import json
import time
from typing import Dict, Any, List

# Configuration
BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 60

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_test(message):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{message}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")

def print_success(message):
    print(f"{GREEN}✅ {message}{RESET}")

def print_error(message):
    print(f"{RED}❌ {message}{RESET}")

def print_info(message):
    print(f"{YELLOW}ℹ️  {message}{RESET}")


class WorkflowTest:
    """Test complete user workflows"""
    
    def __init__(self):
        self.results = []
        self.start_time = time.time()
    
    def test_workflow_1_intelligent_search(self):
        """
        Workflow 1: Intelligent UAT Search
        User searches for UATs → System analyzes query → Returns relevant results
        Services: Context Analyzer → LLM Classifier → Search → Enhanced Matching
        """
        print_test("WORKFLOW 1: Intelligent UAT Search Pipeline")
        
        workflow_steps = []
        test_query = "I need to test Azure Active Directory authentication with SSO"
        
        # Step 1: Analyze context for the query
        print("\n📊 Step 1: Context Analysis")
        try:
            response = requests.post(
                f"{BASE_URL}/api/context/analyze",
                json={"text": test_query},
                timeout=30
            )
            assert response.status_code == 200
            context = response.json()
            print_success(f"Context analyzed: {len(context.get('azure_services', []))} Azure services detected")
            print_info(f"Products: {', '.join(context.get('microsoft_products', [])[:3])}")
            workflow_steps.append(("Context Analysis", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Context analysis failed: {str(e)}")
            workflow_steps.append(("Context Analysis", False, 0))
        
        # Step 2: Classify the query
        print("\n🏷️  Step 2: Query Classification")
        try:
            response = requests.post(
                f"{BASE_URL}/api/classify/classify",
                json={"text": test_query},
                timeout=30
            )
            assert response.status_code == 200
            classification = response.json()
            print_success(f"Classified as: {classification['category']}")
            print_info(f"Intent: {classification['intent']} | Confidence: {classification['confidence']:.2f}")
            workflow_steps.append(("Classification", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Classification failed: {str(e)}")
            workflow_steps.append(("Classification", False, 0))
        
        # Step 3: Search for UATs
        print("\n🔍 Step 3: UAT Search")
        try:
            response = requests.post(
                f"{BASE_URL}/api/search/search",
                json={"query": test_query, "limit": 5},
                timeout=30
            )
            assert response.status_code == 200
            search_results = response.json()
            print_success(f"Found {len(search_results.get('results', []))} UATs")
            if search_results.get('results'):
                top_result = search_results['results'][0]
                print_info(f"Top match: {top_result.get('title', 'N/A')} (score: {top_result.get('score', 0):.2f})")
            workflow_steps.append(("UAT Search", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"UAT search failed: {str(e)}")
            workflow_steps.append(("UAT Search", False, 0))
        
        # Step 4: Enhanced matching for completeness
        print("\n🎯 Step 4: Completeness Analysis")
        try:
            response = requests.post(
                f"{BASE_URL}/api/matching/analyze/completeness",
                json={"text": test_query},
                timeout=30
            )
            assert response.status_code == 200
            completeness = response.json()
            print_success(f"Completeness: {completeness.get('completeness_score', 0):.1%}")
            print_info(f"Missing elements: {len(completeness.get('missing_elements', []))}")
            workflow_steps.append(("Completeness Analysis", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Completeness analysis failed: {str(e)}")
            workflow_steps.append(("Completeness Analysis", False, 0))
        
        # Workflow summary
        print("\n" + "="*70)
        success_count = sum(1 for _, success, _ in workflow_steps if success)
        total_time = sum(time for _, _, time in workflow_steps)
        
        print(f"\n📊 Workflow 1 Summary:")
        for step, success, duration in workflow_steps:
            status = "✅" if success else "❌"
            print(f"  {status} {step}: {duration:.2f}s")
        print(f"\n  Success Rate: {success_count}/{len(workflow_steps)} ({success_count/len(workflow_steps)*100:.0f}%)")
        print(f"  Total Time: {total_time:.2f}s")
        
        return success_count == len(workflow_steps)
    
    def test_workflow_2_semantic_search(self):
        """
        Workflow 2: Semantic Search with Vector Similarity
        User query → Generate embeddings → Vector search → Return similar items
        Services: Embedding → Vector Search
        """
        print_test("WORKFLOW 2: Semantic Search with Vector Similarity")
        
        workflow_steps = []
        
        # Step 1: Index test data
        print("\n📥 Step 1: Index Test UATs")
        test_uats = [
            {
                "id": "e2e-001",
                "title": "Azure AD SSO Authentication",
                "description": "Test single sign-on with Azure Active Directory for enterprise users"
            },
            {
                "id": "e2e-002",
                "title": "Database Performance Testing",
                "description": "Verify Azure SQL Database query performance under load"
            },
            {
                "id": "e2e-003",
                "title": "API Rate Limiting",
                "description": "Test API throttling and rate limit enforcement"
            }
        ]
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/vector/index",
                json={
                    "collection_name": "e2e_test",
                    "items": test_uats,
                    "force_reindex": True
                },
                timeout=120
            )
            assert response.status_code == 200
            result = response.json()
            print_success(f"Indexed {result['indexed_count']} UATs")
            workflow_steps.append(("Index UATs", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Indexing failed: {str(e)}")
            workflow_steps.append(("Index UATs", False, 0))
            return False
        
        # Step 2: Semantic search
        print("\n🔍 Step 2: Semantic Search")
        try:
            response = requests.post(
                f"{BASE_URL}/api/vector/search",
                json={
                    "query": "testing user authentication and login",
                    "collection_name": "e2e_test",
                    "top_k": 2,
                    "similarity_threshold": 0.3
                },
                timeout=60
            )
            assert response.status_code == 200
            search_results = response.json()
            print_success(f"Found {search_results['count']} similar items")
            if search_results.get('results'):
                top_result = search_results['results'][0]
                print_info(f"Top match: {top_result['item_id']} (similarity: {top_result['similarity']:.4f})")
                print_info(f"Title: {top_result['title']}")
            workflow_steps.append(("Semantic Search", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Semantic search failed: {str(e)}")
            workflow_steps.append(("Semantic Search", False, 0))
        
        # Step 3: Duplicate detection
        print("\n🔎 Step 3: Duplicate Detection")
        try:
            response = requests.post(
                f"{BASE_URL}/api/vector/search/similar",
                json={
                    "title": "Azure Active Directory Login",
                    "description": "Test SSO authentication",
                    "top_k": 2
                },
                timeout=60
            )
            assert response.status_code == 200
            duplicates = response.json()
            print_success(f"Duplicate check complete: {duplicates['count']} potential duplicates")
            if duplicates.get('results'):
                for i, dup in enumerate(duplicates['results'][:2], 1):
                    print_info(f"  {i}. {dup['item_id']} (similarity: {dup['similarity']:.4f})")
            workflow_steps.append(("Duplicate Detection", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Duplicate detection failed: {str(e)}")
            workflow_steps.append(("Duplicate Detection", False, 0))
        
        # Cleanup
        print("\n🧹 Step 4: Cleanup Test Data")
        try:
            requests.delete(f"{BASE_URL}/api/vector/collections/e2e_test", timeout=10)
            print_success("Test data cleaned up")
            workflow_steps.append(("Cleanup", True, 0))
        except:
            print_info("Cleanup failed (not critical)")
        
        # Workflow summary
        print("\n" + "="*70)
        success_count = sum(1 for _, success, _ in workflow_steps if success)
        total_time = sum(time for _, _, time in workflow_steps)
        
        print(f"\n📊 Workflow 2 Summary:")
        for step, success, duration in workflow_steps:
            status = "✅" if success else "❌"
            print(f"  {status} {step}: {duration:.2f}s" if duration > 0 else f"  {status} {step}")
        print(f"\n  Success Rate: {success_count}/{len(workflow_steps)} ({success_count/len(workflow_steps)*100:.0f}%)")
        print(f"  Total Time: {total_time:.2f}s")
        
        return success_count >= len(workflow_steps) - 1  # Allow cleanup to fail
    
    def test_workflow_3_uat_lifecycle(self):
        """
        Workflow 3: Complete UAT Lifecycle
        Create UAT → Analyze → Classify → Search similar → Update → Delete
        Services: UAT Management → Context Analyzer → LLM Classifier → Vector Search
        """
        print_test("WORKFLOW 3: Complete UAT Lifecycle Management")
        
        workflow_steps = []
        uat_id = None
        
        # Step 1: Create a new UAT
        print("\n➕ Step 1: Create New UAT")
        new_uat = {
            "title": "E2E Test - Mobile App Performance",
            "description": "Test mobile application performance on iOS and Android devices under various network conditions",
            "status": "draft",
            "priority": "medium"
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/uat/uats",
                json=new_uat,
                timeout=30
            )
            assert response.status_code == 200
            uat = response.json()
            uat_id = uat.get('id')
            print_success(f"Created UAT: {uat_id}")
            print_info(f"Title: {uat.get('title')}")
            workflow_steps.append(("Create UAT", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"UAT creation failed: {str(e)}")
            workflow_steps.append(("Create UAT", False, 0))
            return False
        
        # Step 2: Analyze UAT context
        print("\n📊 Step 2: Analyze UAT Context")
        try:
            response = requests.post(
                f"{BASE_URL}/api/context/analyze",
                json={"text": new_uat['description']},
                timeout=30
            )
            assert response.status_code == 200
            context = response.json()
            print_success(f"Context analyzed")
            print_info(f"Technologies: {', '.join(context.get('technologies', [])[:3])}")
            workflow_steps.append(("Analyze Context", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Context analysis failed: {str(e)}")
            workflow_steps.append(("Analyze Context", False, 0))
        
        # Step 3: Classify UAT
        print("\n🏷️  Step 3: Classify UAT")
        try:
            response = requests.post(
                f"{BASE_URL}/api/classify/classify",
                json={"text": f"{new_uat['title']}. {new_uat['description']}"},
                timeout=30
            )
            assert response.status_code == 200
            classification = response.json()
            print_success(f"Classified: {classification['category']}")
            print_info(f"Business Impact: {classification.get('business_impact', 'unknown')}")
            workflow_steps.append(("Classify UAT", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Classification failed: {str(e)}")
            workflow_steps.append(("Classify UAT", False, 0))
        
        # Step 4: Search for similar UATs
        print("\n🔍 Step 4: Find Similar UATs")
        try:
            response = requests.post(
                f"{BASE_URL}/api/search/search",
                json={"query": new_uat['description'], "limit": 3},
                timeout=30
            )
            assert response.status_code == 200
            similar = response.json()
            print_success(f"Found {len(similar.get('results', []))} similar UATs")
            workflow_steps.append(("Find Similar", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"Similarity search failed: {str(e)}")
            workflow_steps.append(("Find Similar", False, 0))
        
        # Step 5: Update UAT
        print("\n✏️  Step 5: Update UAT Status")
        try:
            response = requests.put(
                f"{BASE_URL}/api/uat/uats/{uat_id}",
                json={"status": "in_progress"},
                timeout=30
            )
            assert response.status_code == 200
            print_success("UAT status updated")
            workflow_steps.append(("Update UAT", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"UAT update failed: {str(e)}")
            workflow_steps.append(("Update UAT", False, 0))
        
        # Step 6: Delete UAT (cleanup)
        print("\n🗑️  Step 6: Delete Test UAT")
        try:
            response = requests.delete(
                f"{BASE_URL}/api/uat/uats/{uat_id}",
                timeout=30
            )
            assert response.status_code == 200
            print_success("UAT deleted successfully")
            workflow_steps.append(("Delete UAT", True, response.elapsed.total_seconds()))
        except Exception as e:
            print_error(f"UAT deletion failed: {str(e)}")
            workflow_steps.append(("Delete UAT", False, 0))
        
        # Workflow summary
        print("\n" + "="*70)
        success_count = sum(1 for _, success, _ in workflow_steps if success)
        total_time = sum(time for _, _, time in workflow_steps)
        
        print(f"\n📊 Workflow 3 Summary:")
        for step, success, duration in workflow_steps:
            status = "✅" if success else "❌"
            print(f"  {status} {step}: {duration:.2f}s")
        print(f"\n  Success Rate: {success_count}/{len(workflow_steps)} ({success_count/len(workflow_steps)*100:.0f}%)")
        print(f"  Total Time: {total_time:.2f}s")
        
        return success_count == len(workflow_steps)
    
    def test_all_services_health(self):
        """Verify all 8 services are healthy"""
        print_test("SYSTEM HEALTH CHECK: All 8 Microservices")
        
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
        
        healthy_count = 0
        for name, url in services:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print_success(f"{name}: Healthy")
                    healthy_count += 1
                else:
                    print_error(f"{name}: Unhealthy (status {response.status_code})")
            except Exception as e:
                print_error(f"{name}: Down ({str(e)[:50]}...)")
        
        print(f"\n{'='*70}")
        print(f"Health Status: {healthy_count}/8 services healthy ({healthy_count/8*100:.0f}%)")
        
        return healthy_count == 8


def main():
    """Run all end-to-end workflow tests"""
    print("\n" + "="*70)
    print("🚀 END-TO-END INTEGRATION TESTS - 8 MICROSERVICES")
    print("="*70)
    print("\nTesting complete user workflows across all services...")
    
    workflow = WorkflowTest()
    results = []
    
    # Test 1: System Health
    print_test("Pre-Flight Check: System Health")
    health_ok = workflow.test_all_services_health()
    results.append(("System Health Check", health_ok))
    
    if not health_ok:
        print_error("\n⚠️  WARNING: Not all services are healthy!")
        print_info("Some tests may fail. Consider running: .\\start_all_services.ps1\n")
    
    # Test 2: Workflow 1 - Intelligent Search
    try:
        result = workflow.test_workflow_1_intelligent_search()
        results.append(("Workflow 1: Intelligent Search", result))
    except Exception as e:
        print_error(f"Workflow 1 crashed: {str(e)}")
        results.append(("Workflow 1: Intelligent Search", False))
    
    # Test 3: Workflow 2 - Semantic Search
    try:
        result = workflow.test_workflow_2_semantic_search()
        results.append(("Workflow 2: Semantic Search", result))
    except Exception as e:
        print_error(f"Workflow 2 crashed: {str(e)}")
        results.append(("Workflow 2: Semantic Search", False))
    
    # Test 4: Workflow 3 - UAT Lifecycle
    try:
        result = workflow.test_workflow_3_uat_lifecycle()
        results.append(("Workflow 3: UAT Lifecycle", result))
    except Exception as e:
        print_error(f"Workflow 3 crashed: {str(e)}")
        results.append(("Workflow 3: UAT Lifecycle", False))
    
    # Final Summary
    total_time = time.time() - workflow.start_time
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print("\n" + "="*70)
    print("📊 FINAL TEST SUMMARY")
    print("="*70)
    
    for name, result in results:
        status = f"{GREEN}✅ PASS{RESET}" if result else f"{RED}❌ FAIL{RESET}"
        print(f"{status}: {name}")
    
    print(f"\n{'='*70}")
    print(f"Passed: {passed}/{total} ({passed/total*100:.0f}%)")
    print(f"Total Test Time: {total_time:.2f}s")
    print(f"{'='*70}")
    
    if passed == total:
        print(f"\n{GREEN}🎉 All end-to-end workflows passed!{RESET}")
        print(f"{GREEN}✅ System is fully operational{RESET}\n")
        return 0
    else:
        print(f"\n{YELLOW}⚠️  {total - passed} workflow(s) failed{RESET}")
        print(f"{YELLOW}Review errors above for details{RESET}\n")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
