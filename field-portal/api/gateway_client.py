"""
Gateway Client — HTTP client for calling existing microservices via API Gateway.

Reuses the same agent endpoints (ports 8001-8007) via the gateway (:8000).
This is a typed async wrapper — the field portal API is async (unlike the sync Flask app).
"""

import httpx
import time
import os
import logging
from typing import Dict, List, Optional, Any

from .config import API_GATEWAY_URL

logger = logging.getLogger("field-portal.gateway")

# Timeout settings (seconds)
DEFAULT_TIMEOUT = 30.0
SEARCH_TIMEOUT = 60.0  # searches can be slow
LLM_TIMEOUT = 45.0     # LLM calls can be slow


class GatewayError(Exception):
    """Raised when the API Gateway returns an error."""
    def __init__(self, status_code: int, detail: str, endpoint: str):
        self.status_code = status_code
        self.detail = detail
        self.endpoint = endpoint
        super().__init__(f"Gateway {status_code} on {endpoint}: {detail}")


class GatewayClient:
    """
    Async HTTP client for calling the API Gateway.
    
    All existing microservices are reached through the gateway:
      /api/matching/*    → enhanced-matching :8003
      /api/context/*     → context-analyzer :8001
      /api/search/*      → search-service :8002 
      /api/classifier/*  → llm-classifier :8005
      /api/embeddings/*  → embedding-service :8006
      /api/vector/*      → vector-search :8007
      /api/uat/*         → uat-management :8004
    """

    def __init__(self, base_url: str = API_GATEWAY_URL):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(DEFAULT_TIMEOUT),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _post(self, endpoint: str, data: Dict, timeout: float = DEFAULT_TIMEOUT) -> Dict:
        client = await self._get_client()
        start = time.monotonic()
        try:
            resp = await client.post(endpoint, json=data, timeout=timeout)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info(f"POST {endpoint} → {resp.status_code} ({elapsed_ms:.0f}ms)")
            if resp.status_code >= 400:
                raise GatewayError(resp.status_code, resp.text[:500], endpoint)
            return resp.json()
        except httpx.ConnectError:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error(f"POST {endpoint} CONNECTION FAILED after {elapsed_ms:.0f}ms")
            raise GatewayError(503, "Gateway not reachable", endpoint)
        except httpx.TimeoutException:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error(f"POST {endpoint} TIMEOUT after {elapsed_ms:.0f}ms")
            raise GatewayError(504, "Gateway timeout", endpoint)

    async def _get(self, endpoint: str, params: Optional[Dict] = None, timeout: float = DEFAULT_TIMEOUT) -> Dict:
        client = await self._get_client()
        start = time.monotonic()
        try:
            resp = await client.get(endpoint, params=params, timeout=timeout)
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.info(f"GET {endpoint} → {resp.status_code} ({elapsed_ms:.0f}ms)")
            if resp.status_code >= 400:
                raise GatewayError(resp.status_code, resp.text[:500], endpoint)
            return resp.json()
        except httpx.ConnectError:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error(f"GET {endpoint} CONNECTION FAILED after {elapsed_ms:.0f}ms")
            raise GatewayError(503, "Gateway not reachable", endpoint)
        except httpx.TimeoutException:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error(f"GET {endpoint} TIMEOUT after {elapsed_ms:.0f}ms")
            raise GatewayError(504, "Gateway timeout", endpoint)

    # ================================================================
    # Health
    # ================================================================

    async def check_health(self) -> bool:
        """Check if the gateway is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get("/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    # ================================================================
    # Quality Analysis (enhanced-matching :8003)
    # ================================================================

    async def analyze_completeness(self, title: str, description: str, impact: str = "") -> Dict:
        """Analyze input completeness — mirrors AIAnalyzer.analyze_completeness()."""
        return await self._post("/api/matching/analyze-completeness", {
            "title": title,
            "description": description,
            "impact": impact,
        })

    # ================================================================
    # Context Analysis (enhanced-matching :8003 → hybrid analyzer)
    # ================================================================

    async def analyze_context(self, title: str, description: str, impact: str = "") -> Dict:
        """Full context analysis — mirrors EnhancedMatcher.analyze_context_for_evaluation()."""
        return await self._post("/api/matching/analyze-context", {
            "title": title,
            "description": description,
            "impact": impact,
        }, timeout=LLM_TIMEOUT)

    # ================================================================
    # Classification (context-analyzer :8001, llm-classifier :8005)
    # ================================================================

    async def classify(self, title: str, description: str, impact: str = "") -> Dict:
        """Direct context analysis — mirrors IntelligentContextAnalyzer.analyze()."""
        return await self._post("/api/context/analyze", {
            "title": title,
            "description": description,
            "impact": impact,
        }, timeout=LLM_TIMEOUT)

    async def llm_classify(self, text: str, title: str = "") -> Dict:
        """LLM classification — mirrors LLMClassifier.classify()."""
        return await self._post("/api/classifier/classify", {
            "text": text,
            "title": title,
        }, timeout=LLM_TIMEOUT)

    # ================================================================
    # Resource Search (search-service :8002)
    # ================================================================

    async def search_resources(
        self,
        title: str,
        description: str,
        category: str,
        intent: str,
        domain_entities: Dict[str, List[str]],
        deep_search: bool = False,
    ) -> Dict:
        """Search all resource sources — mirrors ResourceSearchService.search_all()."""
        return await self._post("/api/search/", {
            "title": title,
            "description": description,
            "category": category,
            "intent": intent,
            "domain_entities": domain_entities,
            "deep_search": deep_search,
        }, timeout=SEARCH_TIMEOUT)

    # ================================================================
    # UAT Search (enhanced-matching :8003 → ADO)
    # ================================================================

    async def search_related_uats(
        self,
        title: str,
        description: str,
        impact: str = "",
        search_mode: str = "combined",
        max_results: int = 10,
    ) -> Dict:
        """Search for similar UATs — mirrors EnhancedMatcher.search_related_uats()."""
        return await self._post("/api/matching/search", {
            "title": title,
            "description": description,
            "impact": impact,
            "search_mode": search_mode,
            "max_results": max_results,
        }, timeout=SEARCH_TIMEOUT)

    # ================================================================
    # Embeddings / Vector Search (embedding :8006, vector :8007)
    # ================================================================

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding — mirrors EmbeddingService.generate_embedding()."""
        result = await self._post("/api/embeddings/embed", {"text": text}, timeout=LLM_TIMEOUT)
        return result.get("embedding", [])

    async def search_similar(
        self,
        query: str,
        collection: str = "uats",
        top_k: int = 10,
        threshold: float = 0.75,
    ) -> List[Dict]:
        """Vector similarity search — mirrors VectorSearchService.search_similar()."""
        result = await self._post("/api/vector/search", {
            "query": query,
            "collection": collection,
            "top_k": top_k,
            "threshold": threshold,
        })
        return result.get("results", [])


# Singleton for app lifetime
_gateway: Optional[GatewayClient] = None


def get_gateway() -> GatewayClient:
    """Get the singleton gateway client."""
    global _gateway
    if _gateway is None:
        _gateway = GatewayClient()
    return _gateway
