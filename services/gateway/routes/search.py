"""
Search API Routes
Handles search operations by routing to Search Service microservice
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Search Service microservice endpoint
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://localhost:8002")

class ComprehensiveSearchRequest(BaseModel):
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

@router.post("/", response_model=SearchResponse)
async def search_resources(request: ComprehensiveSearchRequest):
    """
    Comprehensive search across multiple data sources
    
    Routes to Search Service microservice which searches:
    - Microsoft Learn documentation
    - Similar/alternative Azure products
    - Regional service availability
    - Capacity guidance
    - Retirement information
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{SEARCH_SERVICE_URL}/search",
                json={
                    "title": request.title,
                    "description": request.description,
                    "category": request.category,
                    "intent": request.intent,
                    "domain_entities": request.domain_entities,
                    "deep_search": request.deep_search
                }
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Search Service microservice unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error communicating with Search Service: {str(e)}"
        )

@router.get("/hybrid")
async def hybrid_search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100)
):
    """
    Hybrid search combining vector and keyword search
    
    Future: Routes to Search Service with hybrid capabilities
    """
    # TODO: Route to Search Service microservice
    return {
        "query": query,
        "limit": limit,
        "results": [],
        "message": "Search Service not yet deployed (Phase 5)"
    }
