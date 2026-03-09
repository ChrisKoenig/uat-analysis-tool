"""
Search Service Microservice
Handles comprehensive resource searches across multiple data sources
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import sys
import os
import logging

# Add parent directory to path to import search_service
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, _project_root)
sys.path.insert(0, os.path.join(_project_root, 'apps'))

from shared.search_service import ResourceSearchService, ComprehensiveSearchResults, SearchResult

# Initialize FastAPI app
app = FastAPI(
    title="Search Service",
    description="Comprehensive resource search for Azure issues",
    version="1.0.0"
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Application Insights if available
try:
    from azure.monitor.opentelemetry import configure_azure_monitor
    from dotenv import load_dotenv
    
    load_dotenv()
    
    connection_string = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
    if connection_string:
        configure_azure_monitor(connection_string=connection_string)
        logger.info("[OK] Application Insights enabled")
    else:
        logger.warning("[WARN] Application Insights connection string not found")
except ImportError:
    logger.warning("[WARN] Azure Monitor OpenTelemetry not installed")

# Initialize search service
search_service = ResourceSearchService(use_deep_search=False)

# Request/Response Models
class SearchRequest(BaseModel):
    title: str
    description: str
    category: str
    intent: str
    domain_entities: Dict[str, List[str]]
    deep_search: Optional[bool] = False

class SearchResultModel(BaseModel):
    title: str
    url: str
    snippet: str
    source: str
    relevance_score: float

class SearchResponse(BaseModel):
    search_id: str
    timestamp: str
    learn_docs: List[SearchResultModel]
    similar_products: List[Dict[str, str]]
    regional_options: List[Dict[str, Any]]
    capacity_guidance: Optional[Dict[str, Any]]  # Changed from Dict[str, str] to Dict[str, Any]
    retirement_info: Optional[Dict[str, Any]]
    search_metadata: Dict[str, Any]

# Endpoints
@app.post("/search", response_model=SearchResponse)
async def search_resources(request: SearchRequest):
    """
    Perform comprehensive search across multiple data sources
    
    Searches for:
    - Microsoft Learn documentation
    - Similar/alternative Azure products
    - Regional service availability
    - Capacity guidance
    - Retirement information
    """
    try:
        logger.info(f"Searching for: {request.title[:50]}...")
        
        # Update deep search setting if requested
        if request.deep_search:
            search_service.use_deep_search = True
        
        # Perform search
        results = search_service.search_all(
            title=request.title,
            description=request.description,
            category=request.category,
            intent=request.intent,
            domain_entities=request.domain_entities
        )
        
        # Convert dataclass results to response model
        search_id = f"SEARCH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        response = SearchResponse(
            search_id=search_id,
            timestamp=datetime.utcnow().isoformat(),
            learn_docs=[
                SearchResultModel(
                    title=doc.title,
                    url=doc.url,
                    snippet=doc.snippet,
                    source=doc.source,
                    relevance_score=doc.relevance_score
                ) for doc in results.learn_docs
            ],
            similar_products=results.similar_products,
            regional_options=results.regional_options,
            capacity_guidance=results.capacity_guidance,
            retirement_info=results.retirement_info,
            search_metadata=results.search_metadata
        )
        
        logger.info(f"Search complete: {search_id}")
        return response
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "search-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/info")
async def service_info():
    """Service information endpoint"""
    return {
        "service": "search-service",
        "description": "Comprehensive resource search for Azure issues",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/search", "method": "POST", "description": "Comprehensive resource search"},
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/info", "method": "GET", "description": "Service information"}
        ],
        "data_sources": [
            "Microsoft Learn Documentation",
            "Azure Products Database",
            "Regional Service Availability",
            "Capacity Guidance",
            "Service Retirement Information"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Search Service on port 8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)
