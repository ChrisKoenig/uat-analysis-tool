"""
LLM Classifier Service - Microservice Wrapper
v1.0 - Phase 8: Microservices Transformation

Microservice for AI-powered classification using GPT-4.
Provides endpoints for:
- Classifying customer inquiries (category, intent, business impact)
- Batch classification
- Cache management
- Service health and info

Port: 8005
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import sys
import os
import logging

# Add parent directory to path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(_project_root)
sys.path.append(os.path.join(_project_root, 'apps'))

# Import LLM Classifier
from shared.llm_classifier import LLMClassifier, ClassificationResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="LLM Classifier Service",
    description="AI-powered classification using GPT-4 for intelligent context analysis",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ClassifyRequest(BaseModel):
    """Request for single classification"""
    title: str
    description: str
    impact: Optional[str] = "medium"
    pattern_features: Optional[Dict[str, Any]] = None
    use_cache: Optional[bool] = True

class ClassifyResponse(BaseModel):
    """Response from classification"""
    category: str
    intent: str
    business_impact: str
    confidence: float
    reasoning: str
    pattern_features: Optional[Dict[str, Any]] = None

class BatchClassifyRequest(BaseModel):
    """Request for batch classification"""
    items: List[ClassifyRequest]
    use_cache: Optional[bool] = True

class BatchClassifyResponse(BaseModel):
    """Response from batch classification"""
    results: List[ClassifyResponse]
    total: int
    successful: int
    failed: int

# Global classifier (initialized on startup)
classifier = None

@app.on_event("startup")
async def startup_event():
    """Initialize the LLM classifier service on startup"""
    global classifier
    
    logger.info("LLM Classifier Service starting up...")
    
    try:
        classifier = LLMClassifier()
        logger.info("LLM Classifier initialized")
        logger.info("Azure OpenAI integration ready")
    except Exception as e:
        logger.error(f"Failed to initialize LLM Classifier: {e}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if classifier is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "status": "healthy",
        "service": "llm-classifier",
        "version": "1.0.0",
        "classifier_ready": classifier is not None
    }

@app.get("/info")
async def service_info():
    """Service information endpoint"""
    return {
        "service": "llm-classifier",
        "version": "1.0.0",
        "description": "AI-powered classification using GPT-4",
        "model": classifier.model if classifier else "not initialized",
        "deployment": classifier.deployment if classifier else "not initialized",
        "endpoints": {
            "/classify": "Classify single inquiry",
            "/classify/batch": "Classify multiple inquiries",
            "/cache/stats": "Get cache statistics",
            "/cache/clear": "Clear cache",
            "/health": "Health check",
            "/info": "Service information"
        }
    }

@app.post("/classify", response_model=ClassifyResponse)
async def classify(request: ClassifyRequest):
    """
    Classify a single customer inquiry.
    
    Uses GPT-4 to analyze the inquiry and determine:
    - Category (compliance, technical support, feature request, etc.)
    - Intent (seeking guidance, reporting issue, etc.)
    - Business impact (critical, high, medium, low)
    - Confidence score
    - Reasoning for classification
    """
    if classifier is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Classifying: {request.title[:50]}...")
        
        # Classify using LLM
        result = classifier.classify(
            title=request.title,
            description=request.description,
            impact=request.impact,
            pattern_features=request.pattern_features,
            use_cache=request.use_cache
        )
        
        logger.info(f"Classified as: {result.category} / {result.intent} (confidence: {result.confidence:.2f})")
        
        return ClassifyResponse(
            category=result.category,
            intent=result.intent,
            business_impact=result.business_impact,
            confidence=result.confidence,
            reasoning=result.reasoning,
            pattern_features=result.pattern_features
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_batch(request: BatchClassifyRequest):
    """
    Classify multiple customer inquiries in batch.
    
    Processes multiple inquiries efficiently with caching.
    Returns results for all items with success/failure counts.
    """
    if classifier is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Batch classifying {len(request.items)} items...")
        
        # Convert requests to classifier format
        items = []
        for item in request.items:
            items.append({
                "title": item.title,
                "description": item.description,
                "impact": item.impact or "medium",
                "pattern_features": item.pattern_features
            })
        
        # Classify batch
        results = classifier.classify_batch(items, use_cache=request.use_cache)
        
        # Convert results to response format
        responses = []
        successful = 0
        failed = 0
        
        for result in results:
            responses.append(ClassifyResponse(
                category=result.category,
                intent=result.intent,
                business_impact=result.business_impact,
                confidence=result.confidence,
                reasoning=result.reasoning,
                pattern_features=result.pattern_features
            ))
            
            if result.confidence > 0.5:
                successful += 1
            else:
                failed += 1
        
        logger.info(f"Batch complete: {successful} successful, {failed} low-confidence")
        
        return BatchClassifyResponse(
            results=responses,
            total=len(responses),
            successful=successful,
            failed=failed
        )
        
    except Exception as e:
        logger.error(f"Batch classification error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch classification failed: {str(e)}")

@app.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics.
    
    Returns information about cache usage, hit rates, and performance.
    """
    if classifier is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        stats = classifier.get_cache_stats()
        return {
            "cache_enabled": True,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/clear")
async def clear_cache():
    """
    Clear classification cache.
    
    Removes all cached classification results. Useful for forcing
    fresh classifications or clearing outdated cache entries.
    """
    if classifier is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        classifier.clear_cache()
        logger.info("Cache cleared successfully")
        return {
            "success": True,
            "message": "Classification cache cleared"
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("🚀 LLM Classifier Service - Starting")
    print("="*80)
    print(f"Port: 8005")
    print(f"Features: GPT-4 Classification, Caching, Batch Processing")
    print(f"Operations: Classify, Batch Classify, Cache Management")
    print("="*80)
    
    uvicorn.run(app, host="0.0.0.0", port=8005)
