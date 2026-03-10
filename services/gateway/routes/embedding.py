"""
API Gateway Routes - Embedding Service
Routes embedding requests to the Embedding microservice
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Embedding service URL
EMBEDDING_SERVICE_URL = "http://localhost:8006"

# Request/Response Models
class EmbedRequest(BaseModel):
    text: str
    use_cache: Optional[bool] = True

class EmbedBatchRequest(BaseModel):
    texts: List[str]
    use_cache: Optional[bool] = True

class EmbedContextRequest(BaseModel):
    title: str
    description: str
    impact: Optional[str] = None
    use_cache: Optional[bool] = True

class SimilarityRequest(BaseModel):
    embedding1: List[float]
    embedding2: List[float]

@router.post("/embed")
async def embed_text(request: EmbedRequest):
    """
    Generate embedding for a single text.
    
    Uses Azure OpenAI text-embedding-3-large model.
    Returns 3072-dimensional embedding vector.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EMBEDDING_SERVICE_URL}/embed",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Embedding service error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Embedding failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to embedding service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable"
        )

@router.post("/embed/batch")
async def embed_batch(request: EmbedBatchRequest):
    """
    Generate embeddings for multiple texts.
    
    Efficiently processes multiple texts with caching support.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{EMBEDDING_SERVICE_URL}/embed/batch",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Batch embedding error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Batch embedding failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to embedding service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable"
        )

@router.post("/embed/context")
async def embed_context(request: EmbedContextRequest):
    """
    Generate embeddings for a context (title + description + impact).
    
    Returns separate embeddings and a weighted combined embedding.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EMBEDDING_SERVICE_URL}/embed/context",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Context embedding error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Context embedding failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to embedding service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable"
        )

@router.post("/similarity")
async def calculate_similarity(request: SimilarityRequest):
    """
    Calculate cosine similarity between two embeddings.
    
    Returns similarity score between 0 and 1.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{EMBEDDING_SERVICE_URL}/similarity",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Similarity calculation error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Similarity calculation failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to embedding service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable"
        )

@router.get("/cache/stats")
async def get_cache_stats():
    """Get embedding cache statistics"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{EMBEDDING_SERVICE_URL}/cache/stats")
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Connection error to embedding service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable"
        )

@router.post("/cache/clear")
async def clear_cache():
    """Clear embedding cache"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{EMBEDDING_SERVICE_URL}/cache/clear")
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Connection error to embedding service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable"
        )

@router.post("/cache/cleanup")
async def cleanup_cache():
    """Clean up expired cache entries"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{EMBEDDING_SERVICE_URL}/cache/cleanup")
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Connection error to embedding service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable"
        )
