"""
MICROSERVICES CLIENT LIBRARY
=============================
HTTP client wrapper for calling microservices via API Gateway
Provides drop-in replacements for direct library imports

DEBUG LOGGING:
- All HTTP calls are logged with timing information
- Errors include full request/response details
- Can be enabled/disabled via DEBUG_MICROSERVICES env var
"""

import requests
from typing import Dict, List, Optional, Any
import json
import time
import os

# API Gateway base URL
API_GATEWAY = "http://localhost:8000"

# Debug logging flag
DEBUG_ENABLED = os.environ.get('DEBUG_MICROSERVICES', '1') == '1'

def debug_log(message: str, level: str = "INFO"):
    """Log debug messages if debug is enabled"""
    if DEBUG_ENABLED:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [MICROSERVICES-{level}] {message}")

class MicroservicesClient:
    """Base client for microservices communication"""
    
    def __init__(self, base_url: str = API_GATEWAY):
        self.base_url = base_url
        self.timeout = 30  # 30 seconds timeout
        debug_log(f"Initialized client with base_url: {base_url}")
    
    def _post(self, endpoint: str, data: Dict) -> Dict:
        """Make POST request to microservice"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            debug_log(f"POST {endpoint} - Request size: {len(json.dumps(data))} bytes")
            response = requests.post(url, json=data, timeout=self.timeout)
            elapsed = (time.time() - start_time) * 1000  # ms
            
            response.raise_for_status()
            result = response.json()
            
            debug_log(f"POST {endpoint} - Success in {elapsed:.0f}ms - Response size: {len(json.dumps(result))} bytes")
            return result
            
        except requests.exceptions.Timeout as e:
            elapsed = (time.time() - start_time) * 1000
            debug_log(f"POST {endpoint} - TIMEOUT after {elapsed:.0f}ms", "ERROR")
            debug_log(f"Request data: {json.dumps(data, indent=2)[:500]}...", "ERROR")
            print(f"[ERROR] Microservice timeout: {endpoint} ({elapsed:.0f}ms)")
            raise
            
        except requests.exceptions.RequestException as e:
            elapsed = (time.time() - start_time) * 1000
            debug_log(f"POST {endpoint} - FAILED after {elapsed:.0f}ms", "ERROR")
            debug_log(f"Error: {str(e)}", "ERROR")
            debug_log(f"Request data: {json.dumps(data, indent=2)[:500]}...", "ERROR")
            
            if hasattr(e, 'response') and e.response is not None:
                debug_log(f"Response status: {e.response.status_code}", "ERROR")
                debug_log(f"Response body: {e.response.text[:500]}...", "ERROR")
            
            print(f"[ERROR] Microservice call failed: {endpoint}")
            print(f"[ERROR] {str(e)}")
            raise
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request to microservice"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            debug_log(f"GET {endpoint} - Params: {params}")
            response = requests.get(url, params=params, timeout=self.timeout)
            elapsed = (time.time() - start_time) * 1000  # ms
            
            response.raise_for_status()
            result = response.json()
            
            debug_log(f"GET {endpoint} - Success in {elapsed:.0f}ms - Response size: {len(json.dumps(result))} bytes")
            return result
            
        except requests.exceptions.Timeout as e:
            elapsed = (time.time() - start_time) * 1000
            debug_log(f"GET {endpoint} - TIMEOUT after {elapsed:.0f}ms", "ERROR")
            print(f"[ERROR] Microservice timeout: {endpoint} ({elapsed:.0f}ms)")
            raise
            
        except requests.exceptions.RequestException as e:
            elapsed = (time.time() - start_time) * 1000
            debug_log(f"GET {endpoint} - FAILED after {elapsed:.0f}ms", "ERROR")
            debug_log(f"Error: {str(e)}", "ERROR")
            
            if hasattr(e, 'response') and e.response is not None:
                debug_log(f"Response status: {e.response.status_code}", "ERROR")
                debug_log(f"Response body: {e.response.text[:500]}...", "ERROR")
            
            print(f"[ERROR] Microservice call failed: {endpoint}")
            print(f"[ERROR] {str(e)}")
            raise


class AIAnalyzer(MicroservicesClient):
    """Client for Enhanced Matching AI Analysis
    
    Wraps completeness analysis via HTTP API calls.
    Matches original AIAnalyzer.analyze_completeness() signature.
    """
    
    @classmethod
    def analyze_completeness(cls, title: str, description: str, impact: str = "") -> Dict:
        """Analyze input completeness via microservice
        
        Args:
            title: Issue title
            description: Issue description/scenario
            impact: Business impact (optional)
            
        Returns:
            Dict with quality score, issues, and recommendations
        """
        debug_log(f"AIAnalyzer.analyze_completeness: title='{title[:50]}...', desc_len={len(description)}, impact_len={len(impact)}")
        client = cls()
        return client._post("/api/matching/analyze-completeness", {
            "title": title,
            "description": description,
            "impact": impact
        })


class EnhancedMatcher(MicroservicesClient):
    """Client for Enhanced Matching Search
    
    Wraps UAT search and context evaluation via HTTP API calls.
    Matches original EnhancedMatcher method signatures.
    """
    
    def search_related_uats(self, title: str, description: str, impact: str = "", 
                           search_mode: str = "combined", max_results: int = 10) -> Dict:
        """Search for related UATs via microservice
        
        Args:
            title: Issue title
            description: Issue description
            impact: Business impact
            search_mode: Search strategy (combined, semantic, etc.)
            max_results: Maximum number of results
            
        Returns:
            Dict with search results and metadata
        """
        debug_log(f"EnhancedMatcher.search_related_uats: mode={search_mode}, max={max_results}")
        return self._post("/api/matching/search", {
            "title": title,
            "description": description,
            "impact": impact,
            "search_mode": search_mode,
            "max_results": max_results
        })
    
    def analyze_context_for_evaluation(self, title: str, description: str, impact: str = "") -> Dict:
        """Evaluate context via microservice (matches original EnhancedMatcher.analyze_context_for_evaluation)
        
        Args:
            title: Issue title
            description: Issue description
            impact: Business impact
            
        Returns:
            Dict with context analysis, detected technologies, recommendations
        """
        debug_log(f"EnhancedMatcher.analyze_context_for_evaluation: title='{title[:50]}...'")
        return self._post("/api/matching/analyze-context", {
            "title": title,
            "description": description,
            "impact": impact
        })
    
    @property
    def ado_searcher(self):
        """Provide ado_searcher property for compatibility with original EnhancedMatcher
        
        FIXED 2026-01-19: Creates own AzureDevOpsSearcher instance instead of 
        receiving ado_client via injection. This eliminates AttributeError when 
        UAT selection tried to access non-existent ado_client attribute.
        
        Note: UAT search requires direct ADO access, not available via microservice.
        The searcher handles its own authentication internally.
        """
        if not hasattr(self, '_ado_searcher_proxy'):
            # Create a proxy object that searches ADO directly
            class ADOSearcherProxy:
                def __init__(proxy_self, matcher):
                    proxy_self.matcher = matcher
                    # FIXED: Create our own searcher instance (will handle authentication internally)
                    # Previous approach tried to inject ado_client, causing AttributeError
                    proxy_self._searcher = None
                
                def search_uat_items(proxy_self, title, description=''):
                    """
                    Search for UAT items in Azure DevOps.
                    Creates an AzureDevOpsSearcher instance on first call.
                    """
                    # Lazy-load the searcher to avoid authentication prompts at init
                    if proxy_self._searcher is None:
                        from shared.enhanced_matching import AzureDevOpsSearcher
                        print("[ADO Proxy] Creating AzureDevOpsSearcher instance...", flush=True)
                        proxy_self._searcher = AzureDevOpsSearcher()
                        print("[ADO Proxy] AzureDevOpsSearcher created successfully!", flush=True)
                    
                    # Delegate to the searcher's search_uat_items method
                    return proxy_self._searcher.search_uat_items(
                        title=title,
                        description=description
                    )
            
            self._ado_searcher_proxy = ADOSearcherProxy(self)
        return self._ado_searcher_proxy


class ResourceSearchService(MicroservicesClient):
    """Client for Resource Search"""
    
    def __init__(self, use_deep_search: bool = False):
        super().__init__()
        self.use_deep_search = use_deep_search
    
    def search(self, query: str, max_results: int = 10, 
               categories: Optional[List[str]] = None) -> 'ComprehensiveSearchResults':
        """Search UATs via microservice"""
        response = self._post("/api/search/uats", {
            "query": query,
            "max_results": max_results,
            "categories": categories or []
        })
        
        # Convert response to ComprehensiveSearchResults format
        results = ComprehensiveSearchResults()
        results.uats = [SearchResult(**item) for item in response.get("results", [])]
        results.total_results = response.get("total_results", 0)
        return results
    
    def search_all(self, title: str, description: str, category: str, 
                   intent: str, domain_entities: Dict[str, List[str]]) -> 'ComprehensiveSearchResults':
        """Comprehensive search across all sources via microservice"""
        debug_log(f"ResourceSearchService.search_all: Searching for '{title[:50]}...'")
        
        response = self._post("/api/search/", {
            "title": title,
            "description": description,
            "category": category,
            "intent": intent,
            "domain_entities": domain_entities,
            "deep_search": self.use_deep_search
        })
        
        # Convert response to ComprehensiveSearchResults format with all fields
        results = ComprehensiveSearchResults()
        results.learn_docs = [SearchResult(**item) for item in response.get("learn_docs", [])]
        results.similar_products = response.get("similar_products", [])
        results.regional_options = response.get("regional_options", [])
        results.capacity_guidance = response.get("capacity_guidance")
        results.retirement_info = response.get("retirement_info")
        results.search_metadata = response.get("search_metadata", {})
        
        debug_log(f"ResourceSearchService.search_all: Found {len(results.learn_docs)} learn docs")
        return results


class SearchResult:
    """Search result item"""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        # Ensure required fields exist
        if 'score' not in self.__dict__:
            self.score = 0.0
        if 'title' not in self.__dict__:
            self.title = ""
        if 'description' not in self.__dict__:
            self.description = ""


class ComprehensiveSearchResults:
    """Search results collection"""
    def __init__(self):
        self.uats = []
        self.total_results = 0
        self.features = []
        self.all_items = []


class IntelligentContextAnalyzer(MicroservicesClient):
    """Client for Context Analysis"""
    
    def analyze(self, title: str, description: str = "", impact: str = "") -> Dict:
        """Analyze context via microservice"""
        return self._post("/api/context/analyze", {
            "title": title,
            "description": description,
            "impact": impact
        })


class LLMClassifier(MicroservicesClient):
    """Client for LLM Classification"""
    
    def classify(self, text: str, title: str = "") -> Dict:
        """Classify text via microservice"""
        return self._post("/api/classifier/classify", {
            "text": text,
            "title": title
        })


class EmbeddingService(MicroservicesClient):
    """Client for Embedding Generation"""
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding via microservice"""
        response = self._post("/api/embeddings/embed", {"text": text})
        return response.get("embedding", [])
    
    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts via microservice"""
        response = self._post("/api/embeddings/batch", {"texts": texts})
        return response.get("embeddings", [])


class VectorSearchService(MicroservicesClient):
    """Client for Vector Search"""
    
    def search_similar(self, query: str, collection: str = "uats", 
                      top_k: int = 10, threshold: float = 0.75) -> List[Dict]:
        """Search similar items via microservice"""
        response = self._post("/api/vector/search", {
            "query": query,
            "collection": collection,
            "top_k": top_k,
            "threshold": threshold
        })
        return response.get("results", [])
    
    def detect_duplicates(self, query: str, collection: str = "uats", 
                         threshold: float = 0.70) -> List[Dict]:
        """Detect duplicate items via microservice"""
        response = self._post("/api/vector/duplicates", {
            "query": query,
            "collection": collection,
            "threshold": threshold
        })
        return response.get("duplicates", [])


# Convenience function to check if microservices are available
def check_microservices_health() -> bool:
    """Check if microservices are running and healthy
    
    Returns:
        True if API Gateway health check succeeds, False otherwise
    """
    try:
        debug_log("Checking microservices health...")
        response = requests.get(f"{API_GATEWAY}/health", timeout=5)
        is_healthy = response.status_code == 200
        debug_log(f"Health check result: {'HEALTHY' if is_healthy else 'UNHEALTHY'}")
        return is_healthy
    except Exception as e:
        debug_log(f"Health check failed: {str(e)}", "ERROR")
        return False


def get_service_info() -> Dict:
    """Get information about all microservices
    
    Returns:
        Dict with service information (name, version, routes, etc.)
    """
    try:
        debug_log("Fetching service info...")
        response = requests.get(f"{API_GATEWAY}/info", timeout=5)
        info = response.json() if response.status_code == 200 else {}
        debug_log(f"Service info retrieved: {len(info.get('routes', []))} routes")
        return info
    except Exception as e:
        debug_log(f"Failed to get service info: {str(e)}", "ERROR")
        return {}
