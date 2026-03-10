"""
API Gateway Routes - LLM Classifier Service
Routes classification requests to the LLM Classifier microservice
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# LLM Classifier service URL
CLASSIFIER_SERVICE_URL = "http://localhost:8005"

# Request/Response Models
class ClassifyRequest(BaseModel):
    title: str
    description: str
    impact: Optional[str] = "medium"
    pattern_features: Optional[Dict[str, Any]] = None
    use_cache: Optional[bool] = True

class ClassifyResponse(BaseModel):
    category: str
    intent: str
    business_impact: str
    confidence: float
    reasoning: str
    pattern_features: Optional[Dict[str, Any]] = None

class BatchClassifyRequest(BaseModel):
    items: List[ClassifyRequest]
    use_cache: Optional[bool] = True

class BatchClassifyResponse(BaseModel):
    results: List[ClassifyResponse]
    total: int
    successful: int
    failed: int

@router.post("/classify", response_model=ClassifyResponse)
async def classify_inquiry(request: ClassifyRequest):
    """
    Classify a customer inquiry using GPT-4.
    
    Analyzes the inquiry and returns:
    - Category (compliance, technical support, feature request, etc.)
    - Intent (seeking guidance, reporting issue, etc.)
    - Business impact (critical, high, medium, low)
    - Confidence score
    - Reasoning
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{CLASSIFIER_SERVICE_URL}/classify",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Classification service error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Classification failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to classifier service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Classification service unavailable"
        )

@router.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_batch(request: BatchClassifyRequest):
    """
    Classify multiple customer inquiries in batch.
    
    Efficiently processes multiple inquiries with caching.
    Returns results for all items with success/failure counts.
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{CLASSIFIER_SERVICE_URL}/classify/batch",
                json=request.dict()
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Batch classification error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Batch classification failed: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Connection error to classifier service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Classification service unavailable"
        )

@router.get("/cache/stats")
async def get_cache_stats():
    """Get classification cache statistics"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{CLASSIFIER_SERVICE_URL}/cache/stats")
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Connection error to classifier service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Classification service unavailable"
        )

@router.post("/cache/clear")
async def clear_cache():
    """Clear classification cache"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{CLASSIFIER_SERVICE_URL}/cache/clear")
            response.raise_for_status()
            return response.json()
            
    except httpx.RequestError as e:
        logger.error(f"Connection error to classifier service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Classification service unavailable"
        )
