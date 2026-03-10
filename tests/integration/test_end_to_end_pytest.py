"""
End-to-End Integration Tests — All 8 Microservices

Tests complete user workflows across the entire system.
Requires all services to be running (use start_dev.ps1).

Run with:  pytest tests/integration/test_end_to_end_pytest.py -m integration -v
"""
import pytest
import requests

BASE_URL = "http://localhost:8000"
REQUEST_TIMEOUT = 30


def _service_available():
    """Check if the gateway is reachable."""
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _service_available(), reason="API gateway not running on localhost:8000"),
]


# ── Health checks ────────────────────────────────────────────────────────────

_SERVICES = [
    ("Context Analyzer",  "http://localhost:8001/health"),
    ("Search Service",    "http://localhost:8002/health"),
    ("Enhanced Matching",  "http://localhost:8003/health"),
    ("UAT Management",    "http://localhost:8004/health"),
    ("LLM Classifier",    "http://localhost:8005/health"),
    ("Embedding Service",  "http://localhost:8006/health"),
    ("Vector Search",      "http://localhost:8007/health"),
    ("API Gateway",        "http://localhost:8000/health"),
]


@pytest.mark.parametrize("name,url", _SERVICES, ids=[s[0] for s in _SERVICES])
def test_service_health(name, url):
    r = requests.get(url, timeout=5)
    assert r.status_code == 200, f"{name} unhealthy (status {r.status_code})"


# ── Workflow 1: Intelligent UAT Search ───────────────────────────────────────

class TestWorkflowIntelligentSearch:
    """Search pipeline: Context Analysis → Classification → Search → Completeness."""

    _query = "I need to test Azure Active Directory authentication with SSO"

    def test_context_analysis(self):
        r = requests.post(
            f"{BASE_URL}/api/context/analyze",
            json={"text": self._query},
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "azure_services" in data or "microsoft_products" in data

    def test_query_classification(self):
        r = requests.post(
            f"{BASE_URL}/api/classify/classify",
            json={"text": self._query},
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "category" in data
        assert "confidence" in data

    def test_uat_search(self):
        r = requests.post(
            f"{BASE_URL}/api/search/search",
            json={"query": self._query, "limit": 5},
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        assert "results" in r.json()

    def test_completeness_analysis(self):
        r = requests.post(
            f"{BASE_URL}/api/matching/analyze/completeness",
            json={"text": self._query},
            timeout=REQUEST_TIMEOUT,
        )
        assert r.status_code == 200
        data = r.json()
        assert "completeness_score" in data


# ── Workflow 2: Semantic Search with Vector Similarity ───────────────────────

class TestWorkflowSemanticSearch:
    """Embedding → Vector index → Semantic search → Duplicate detection."""

    _collection = "e2e_pytest"
    _test_uats = [
        {"id": "e2e-001", "title": "Azure AD SSO Authentication",
         "description": "Test single sign-on with Azure Active Directory for enterprise users"},
        {"id": "e2e-002", "title": "Database Performance Testing",
         "description": "Verify Azure SQL Database query performance under load"},
        {"id": "e2e-003", "title": "API Rate Limiting",
         "description": "Test API throttling and rate limit enforcement"},
    ]

    @pytest.fixture(autouse=True)
    def _index_and_cleanup(self):
        """Index test UATs before tests, clean up after."""
        r = requests.post(
            f"{BASE_URL}/api/vector/index",
            json={"collection_name": self._collection, "items": self._test_uats, "force_reindex": True},
            timeout=120,
        )
        assert r.status_code == 200
        yield
        requests.delete(f"{BASE_URL}/api/vector/collections/{self._collection}", timeout=10)

    def test_semantic_search(self):
        r = requests.post(
            f"{BASE_URL}/api/vector/search",
            json={"query": "testing user authentication and login",
                  "collection_name": self._collection, "top_k": 2, "similarity_threshold": 0.3},
            timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] > 0

    def test_duplicate_detection(self):
        r = requests.post(
            f"{BASE_URL}/api/vector/search/similar",
            json={"title": "Azure Active Directory Login",
                  "description": "Test SSO authentication", "top_k": 2},
            timeout=60,
        )
        assert r.status_code == 200
        assert "results" in r.json()


# ── Workflow 3: Complete UAT Lifecycle ───────────────────────────────────────

class TestWorkflowUATLifecycle:
    """Create → Analyze → Classify → Search similar → Update → Delete."""

    _new_uat = {
        "title": "E2E Test - Mobile App Performance",
        "description": "Test mobile application performance on iOS and Android devices under various network conditions",
        "status": "draft",
        "priority": "medium",
    }

    def test_full_lifecycle(self):
        # Create
        r = requests.post(f"{BASE_URL}/api/uat/uats", json=self._new_uat, timeout=REQUEST_TIMEOUT)
        assert r.status_code == 200
        uat_id = r.json().get("id")
        assert uat_id

        try:
            # Analyze context
            r = requests.post(
                f"{BASE_URL}/api/context/analyze",
                json={"text": self._new_uat["description"]},
                timeout=REQUEST_TIMEOUT,
            )
            assert r.status_code == 200

            # Classify
            r = requests.post(
                f"{BASE_URL}/api/classify/classify",
                json={"text": f"{self._new_uat['title']}. {self._new_uat['description']}"},
                timeout=REQUEST_TIMEOUT,
            )
            assert r.status_code == 200

            # Search similar
            r = requests.post(
                f"{BASE_URL}/api/search/search",
                json={"query": self._new_uat["description"], "limit": 3},
                timeout=REQUEST_TIMEOUT,
            )
            assert r.status_code == 200

            # Update
            r = requests.put(
                f"{BASE_URL}/api/uat/uats/{uat_id}",
                json={"status": "in_progress"},
                timeout=REQUEST_TIMEOUT,
            )
            assert r.status_code == 200
        finally:
            # Always clean up
            requests.delete(f"{BASE_URL}/api/uat/uats/{uat_id}", timeout=REQUEST_TIMEOUT)
