"""
Analysis API Routes
Handles analysis requests and routing to Context Analyzer microservice
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# Context Analyzer microservice endpoint
CONTEXT_ANALYZER_URL = os.getenv("CONTEXT_ANALYZER_URL", "http://localhost:8001")

class AnalysisRequest(BaseModel):
    title: str
    description: str
    impact: Optional[str] = None
    metadata: Optional[Dict] = None

class AnalysisResult(BaseModel):
    analysis_id: str
    timestamp: str
    categories: List[str]
    confidence: float
    primary_category: str
    detected_products: List[str]
    detected_services: List[str]
    key_concepts: List[str]
    routing_recommendation: str
    reasoning: Dict
    metadata: Dict

@router.post("/", response_model=AnalysisResult)
async def analyze_text(request: AnalysisRequest):
    """
    Analyze UAT submission by routing to Context Analyzer microservice
    
    This endpoint forwards analysis requests to the Context Analyzer agent
    which runs as an independent microservice on port 8001.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{CONTEXT_ANALYZER_URL}/analyze",
                json={
                    "title": request.title,
                    "description": request.description,
                    "impact": request.impact,
                    "metadata": request.metadata or {}
                }
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Context Analyzer microservice unavailable: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error communicating with Context Analyzer: {str(e)}"
        )

@router.get("/{analysis_id}")
async def get_analysis(analysis_id: str):
    """
    Retrieve analysis results by ID
    
    Future: Routes to Analysis Agent microservice
    """
    # TODO: Route to Analysis Agent microservice
    return {
        "analysis_id": analysis_id,
        "message": "Analysis retrieval not yet implemented (Phase 6)"
    }
