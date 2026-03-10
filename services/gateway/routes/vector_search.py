"""
API Gateway Routes - Vector Search Service
Routes vector search requests to the Vector Search microservice
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Vector Search service URL
VECTOR_SEARCH_SERVICE_URL = "http://localhost:8007"

# Request/Response Models
class IndexItem(BaseModel):
    id: str
    title: str
    description: str
    metadata: Optional[Dict[str, Any]] = None

class IndexRequest(BaseModel):
    collection_name: str
    items: List[IndexItem]
    force_reindex: Optional[bool] = False

class SearchRequest(BaseModel):
    query: str
    collection_name: str
    top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None
    use_cache: Optional[bool] = True

class SearchContextRequest(BaseModel):
    title: str
    description: str
    collection_name: str
    top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None

class FindSimilarRequest(BaseModel):
    title: str
    description: str
    top_k: Optional[int] = 5

@router.post("/index")
async def index_items(request: IndexRequest):
    """
    Index items into a collection for semantic search.
    
    Creates embeddings for each item and stores them in the named collection.
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{VECTOR_SEARCH_SERVICE_URL}/index",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Vector search indexing error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Indexing failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to vector search service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Vector search service unavailable"
        )

@router.post("/search")
async def search(request: SearchRequest):
    """
    Perform semantic similarity search.
    
    Searches for items most similar to the query text.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{VECTOR_SEARCH_SERVICE_URL}/search",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Vector search error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Search failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to vector search service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Vector search service unavailable"
        )

@router.post("/search/context")
async def search_with_context(request: SearchContextRequest):
    """
    Search using title + description context.
    
    Combines title and description for semantic search.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{VECTOR_SEARCH_SERVICE_URL}/search/context",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Context search error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Context search failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to vector search service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Vector search service unavailable"
        )

@router.post("/search/similar")
async def find_similar_issues(request: FindSimilarRequest):
    """
    Find similar issues for duplicate detection.
    
    Uses higher similarity threshold to find potential duplicates.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{VECTOR_SEARCH_SERVICE_URL}/search/similar",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Similar issues search error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Similar issues search failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to vector search service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Vector search service unavailable"
        )

@router.get("/collections")
async def list_collections():
    """List all indexed collections"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{VECTOR_SEARCH_SERVICE_URL}/collections")
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Connection error to vector search service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Vector search service unavailable"
        )

@router.get("/collections/{collection_name}/stats")
async def get_collection_stats(collection_name: str):
    """Get statistics for a specific collection"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{VECTOR_SEARCH_SERVICE_URL}/collections/{collection_name}/stats"
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.text
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to vector search service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Vector search service unavailable"
        )

@router.delete("/collections/{collection_name}")
async def clear_collection(collection_name: str):
    """Clear a specific collection"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{VECTOR_SEARCH_SERVICE_URL}/collections/{collection_name}"
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Connection error to vector search service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Vector search service unavailable"
        )

@router.post("/collections/clear-all")
async def clear_all_collections():
    """Clear all collections"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{VECTOR_SEARCH_SERVICE_URL}/collections/clear-all"
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Connection error to vector search service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Vector search service unavailable"
        )
