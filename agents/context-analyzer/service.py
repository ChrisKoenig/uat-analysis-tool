"""
Context Analyzer Microservice
Extracted from intelligent_context_analyzer.py for microservices architecture
Phase 4: First agent extraction
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../../.env.azure')

# Initialize logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Application Insights setup
APP_INSIGHTS_CONNECTION_STRING = os.getenv('AZURE_APP_INSIGHTS_CONNECTION_STRING')
if APP_INSIGHTS_CONNECTION_STRING:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=APP_INSIGHTS_CONNECTION_STRING)
        logger.info("✅ Application Insights enabled")
    except Exception as e:
        logger.warning(f"⚠️  App Insights init failed: {e}")

# Initialize FastAPI
app = FastAPI(
    title="Context Analyzer Agent",
    description="AI-powered context analysis for IT support issues",
    version="1.0.0"
)

# Request/Response Models
class AnalyzeRequest(BaseModel):
    title: str
    description: str
    impact: Optional[str] = ""
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

# Import the analyzer (will be refactored)
import sys
sys.path.append('../..')
from services.intelligent_context_analyzer import IntelligentContextAnalyzer

# Initialize analyzer
analyzer = IntelligentContextAnalyzer()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "context-analyzer",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/analyze", response_model=AnalysisResult)
async def analyze_context(request: AnalyzeRequest):
    """
    Analyze text submission for context, category, and routing
    
    This endpoint performs comprehensive AI-powered analysis including:
    - Category classification
    - Product/service detection  
    - Intent identification
    - Routing recommendations
    """
    try:
        logger.info(f"Analyzing request: {request.title[:50]}...")
        
        # Perform analysis using existing logic
        result = analyzer.analyze_context(
            title=request.title,
            description=request.description,
            impact=request.impact or ""
        )
        
        # Convert to response format
        analysis_id = f"CA-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        response = AnalysisResult(
            analysis_id=analysis_id,
            timestamp=datetime.utcnow().isoformat(),
            categories=result.categories if hasattr(result, 'categories') else [],
            confidence=result.confidence if hasattr(result, 'confidence') else 0.0,
            primary_category=result.primary_category if hasattr(result, 'primary_category') else "unknown",
            detected_products=result.detected_products if hasattr(result, 'detected_products') else [],
            detected_services=result.detected_services if hasattr(result, 'detected_services') else [],
            key_concepts=result.key_concepts if hasattr(result, 'key_concepts') else [],
            routing_recommendation=result.routing_recommendation if hasattr(result, 'routing_recommendation') else "",
            reasoning=result.reasoning if hasattr(result, 'reasoning') else {},
            metadata={
                "request_metadata": request.metadata or {},
                "analysis_version": "1.0.0"
            }
        )
        
        logger.info(f"Analysis complete: {analysis_id}")
        return response
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/info")
async def service_info():
    """Service information"""
    return {
        "service": "context-analyzer",
        "version": "1.0.0",
        "description": "AI-powered context analysis microservice",
        "endpoints": {
            "analyze": "POST /analyze",
            "health": "GET /health",
            "info": "GET /info"
        },
        "status": "operational"
    }

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("CONTEXT_ANALYZER_PORT", "8001"))
    logger.info(f"Starting Context Analyzer on port {port}")
    
    uvicorn.run(
        "service:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
