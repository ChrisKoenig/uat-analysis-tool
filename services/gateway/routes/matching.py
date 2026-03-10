"""
Enhanced Matching Routes - API Gateway
Phase 6: Routes requests to Enhanced Matching microservice (port 8003)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Enhanced Matching service URL
MATCHING_SERVICE_URL = "http://localhost:8003"

# Request/Response Models
class CompletenessRequest(BaseModel):
    """Request for issue completeness analysis"""
    title: str
    description: str
    impact: Optional[str] = ""

class ContextAnalysisRequest(BaseModel):
    """Request for context analysis"""
    title: str
    description: str
    impact: Optional[str] = ""

class IntelligentSearchRequest(BaseModel):
    """Request for intelligent search"""
    title: str
    description: str
    impact: Optional[str] = ""
    skip_evaluation: bool = False

class ContinueSearchRequest(BaseModel):
    """Request to continue search after evaluation"""
    evaluation_data: Dict[str, Any]

@router.post("/analyze-completeness")
async def analyze_completeness(request: CompletenessRequest):
    """
    Analyze issue completeness and quality.
    Routes to Enhanced Matching service for AI-powered analysis.
    """
    try:
        logger.info(f"🔄 Routing completeness analysis to Enhanced Matching service...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MATCHING_SERVICE_URL}/analyze-completeness",
                json=request.dict()
            )
            response.raise_for_status()
            result = response.json()
            
        logger.info(f"✅ Completeness score: {result.get('completeness_score')}%")
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"❌ Enhanced Matching service error: {e}")
        raise HTTPException(status_code=503, detail=f"Enhanced Matching service unavailable: {str(e)}")

@router.post("/analyze-context")
async def analyze_context(request: ContextAnalysisRequest):
    """
    Perform context analysis for evaluation.
    Routes to Enhanced Matching service for intelligent context understanding.
    """
    try:
        logger.info(f"🔄 Routing context analysis to Enhanced Matching service...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MATCHING_SERVICE_URL}/analyze-context",
                json=request.dict()
            )
            response.raise_for_status()
            result = response.json()
            
        category = result.get('context_analysis', {}).get('category', 'unknown')
        logger.info(f"✅ Context category: {category}")
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"❌ Enhanced Matching service error: {e}")
        raise HTTPException(status_code=503, detail=f"Enhanced Matching service unavailable: {str(e)}")

@router.post("/intelligent-search")
async def intelligent_search(request: IntelligentSearchRequest):
    """
    Perform intelligent multi-source search.
    Routes to Enhanced Matching service for context-aware matching.
    """
    try:
        logger.info(f"🔄 Routing intelligent search to Enhanced Matching service...")
        
        # Longer timeout for search operations (up to 3 minutes)
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{MATCHING_SERVICE_URL}/intelligent-search",
                json=request.dict()
            )
            response.raise_for_status()
            result = response.json()
            
        total_matches = result.get('results', {}).get('total_matches', 0)
        logger.info(f"✅ Search complete: {total_matches} matches")
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"❌ Enhanced Matching service error: {e}")
        raise HTTPException(status_code=503, detail=f"Enhanced Matching service unavailable: {str(e)}")

@router.post("/continue-search")
async def continue_search(request: ContinueSearchRequest):
    """
    Continue search after evaluation approval.
    Routes to Enhanced Matching service with approved context.
    """
    try:
        logger.info(f"🔄 Routing approved search to Enhanced Matching service...")
        
        # Longer timeout for search operations (up to 3 minutes)
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{MATCHING_SERVICE_URL}/continue-search",
                json=request.dict()
            )
            response.raise_for_status()
            result = response.json()
            
        total_matches = result.get('results', {}).get('total_matches', 0)
        logger.info(f"✅ Approved search complete: {total_matches} matches")
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"❌ Enhanced Matching service error: {e}")
        raise HTTPException(status_code=503, detail=f"Enhanced Matching service unavailable: {str(e)}")
