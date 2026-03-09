"""
Enhanced Matching Service - Microservice Wrapper
v1.0 - Phase 6: Microservices Transformation

Microservice for AI-powered issue matching and similarity analysis.
Provides endpoints for:
- Completeness analysis
- Context evaluation
- Intelligent search across multiple sources
- Result compilation with semantic ranking

Port: 8003
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Callable
from contextlib import asynccontextmanager
import sys
import os
from datetime import datetime
import logging

# Add parent directory to path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(_project_root)
sys.path.append(os.path.join(_project_root, 'apps'))

# Import the actual enhanced matching implementation
from shared.enhanced_matching import EnhancedMatcher, ProgressTracker, AIAnalyzer, EnhancedMatchingConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global matcher instance (initialized with None, will be set on startup)
matcher = None
issue_tracker = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the enhanced matcher"""
    global matcher, issue_tracker
    
    # Startup
    logger.info("🚀 Enhanced Matching Service starting up...")
    logger.info("📋 Loading knowledge bases and initializing components...")
    
    # Note: IssueTracker is not available in search_service, setting to None
    issue_tracker = None
    
    # Initialize matcher
    try:
        matcher = EnhancedMatcher(issue_tracker)
        logger.info("✅ Enhanced Matcher initialized successfully")
        logger.info("🔐 Azure DevOps authentication ready")
        logger.info("🧠 AI analysis components loaded")
        logger.info("🎯 Context analyzer ready")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Enhanced Matcher: {e}")
        raise
    
    yield
    
    # Shutdown (if needed)
    logger.info("🔚 Enhanced Matching Service shutting down...")

app = FastAPI(
    title="Enhanced Matching Service",
    description="AI-powered issue matching and similarity analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for API Gateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],  # API Gateway
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class CompletenessRequest(BaseModel):
    """Request for issue completeness analysis"""
    title: str = Field(..., description="Issue title")
    description: str = Field(..., description="Issue description")
    impact: Optional[str] = Field("", description="Business impact statement")

class CompletenessResponse(BaseModel):
    """Response with completeness analysis"""
    is_complete: bool
    issues: List[str]
    suggestions: List[str]
    completeness_score: int
    needs_improvement: bool
    garbage_detected: bool
    garbage_details: Dict[str, Any]

class ContextAnalysisRequest(BaseModel):
    """Request for context analysis"""
    title: str = Field(..., description="Issue title")
    description: str = Field(..., description="Issue description")
    impact: Optional[str] = Field("", description="Business impact statement")

class ContextAnalysisResponse(BaseModel):
    """Response with context analysis for evaluation"""
    original_issue: Dict[str, str]
    context_analysis: Dict[str, Any]
    timestamp: str

class IntelligentSearchRequest(BaseModel):
    """Request for intelligent search"""
    title: str = Field(..., description="Issue title")
    description: str = Field(..., description="Issue description")
    impact: Optional[str] = Field("", description="Business impact statement")
    skip_evaluation: bool = Field(False, description="Skip evaluation and proceed with search")

class ContinueSearchRequest(BaseModel):
    """Request to continue search after evaluation approval"""
    evaluation_data: Dict[str, Any] = Field(..., description="Approved evaluation data with context")

class SearchResultItem(BaseModel):
    """Individual search result item"""
    id: Any
    title: str
    description: str
    similarity: float
    source: str
    url: Optional[str] = None
    created_date: Optional[str] = None
    work_item_type: Optional[str] = None
    state: Optional[str] = None
    match_reasoning: Optional[str] = None
    enhanced_similarity: Optional[float] = None
    context_relevance: Optional[float] = None

class SearchResults(BaseModel):
    """Complete search results"""
    evaluating_retirements: List[Dict[str, Any]]
    uat_items: List[Dict[str, Any]]
    feature_items: List[Dict[str, Any]]
    all_items: List[Dict[str, Any]]
    total_matches: int
    context_analysis: Optional[Dict[str, Any]] = None
    search_strategy_used: Optional[Dict[str, Any]] = None

class IntelligentSearchResponse(BaseModel):
    """Response with intelligent search results"""
    progress: Optional[Dict[str, Any]]
    results: SearchResults

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if matcher is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "status": "healthy",
        "service": "enhanced-matching",
        "version": "1.0.0",
        "components": {
            "matcher": matcher is not None,
            "issue_tracker": issue_tracker is not None,
            "ado_searcher": hasattr(matcher, 'ado_searcher'),
            "context_analyzer": hasattr(matcher, 'context_analyzer'),
            "ai_analyzer": hasattr(matcher, 'ai_analyzer')
        }
    }

@app.get("/info")
async def service_info():
    """Get service information and capabilities"""
    return {
        "name": "Enhanced Matching Service",
        "version": "1.0.0",
        "description": "AI-powered issue matching and similarity analysis",
        "port": 8003,
        "endpoints": {
            "analyze_completeness": "POST /analyze-completeness - Analyze issue completeness",
            "analyze_context": "POST /analyze-context - Perform context analysis for evaluation",
            "intelligent_search": "POST /intelligent-search - Perform intelligent multi-source search",
            "continue_search": "POST /continue-search - Continue search after evaluation approval",
            "health": "GET /health - Health check",
            "info": "GET /info - Service information"
        },
        "capabilities": {
            "ai_completeness_analysis": True,
            "context_evaluation": True,
            "intelligent_routing": True,
            "multi_source_search": True,
            "semantic_ranking": True,
            "azure_devops_integration": True
        }
    }

@app.post("/analyze-completeness", response_model=CompletenessResponse)
async def analyze_completeness(request: CompletenessRequest):
    """
    Analyze the completeness and quality of an issue submission.
    
    Performs AI-powered analysis to detect:
    - Garbage/meaningless input
    - Insufficient detail
    - Missing context
    - Vague descriptions
    
    Returns suggestions for improvement and a completeness score.
    """
    if matcher is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"🔍 Analyzing completeness for: {request.title[:50]}...")
        
        analysis = matcher.ai_analyzer.analyze_completeness(
            request.title,
            request.description,
            request.impact or ""
        )
        
        logger.info(f"✅ Completeness: {analysis['completeness_score']}%, Issues: {len(analysis['issues'])}")
        
        return CompletenessResponse(**analysis)
        
    except Exception as e:
        logger.error(f"❌ Error analyzing completeness: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/analyze-context", response_model=ContextAnalysisResponse)
async def analyze_context(request: ContextAnalysisRequest):
    """
    Perform context analysis for human evaluation.
    
    Uses intelligent context analyzer to understand:
    - Issue category (technical, compliance, feature request, etc.)
    - User intent (information, troubleshooting, feature request, etc.)
    - Business impact and urgency
    - Key concepts and semantic keywords
    - Recommended search strategy
    
    Results are returned for human validation before proceeding with search.
    """
    if matcher is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"🧠 Performing context analysis for: {request.title[:50]}...")
        
        evaluation_data = matcher.analyze_context_for_evaluation(
            request.title,
            request.description,
            request.impact or ""
        )
        
        category = evaluation_data['context_analysis']['category']
        intent = evaluation_data['context_analysis']['intent']
        confidence = evaluation_data['context_analysis']['confidence']
        
        logger.info(f"[ENHANCED-MATCHING DEBUG] Full evaluation_data keys: {list(evaluation_data.keys())}")
        logger.info(f"[ENHANCED-MATCHING DEBUG] Context analysis keys: {list(evaluation_data['context_analysis'].keys())}")
        logger.info(f"[ENHANCED-MATCHING DEBUG] Category type: {type(category)}, Value: '{category}'")
        logger.info(f"[ENHANCED-MATCHING DEBUG] Category display: '{evaluation_data['context_analysis'].get('category_display', 'N/A')}'")
        logger.info(f"✅ Context: Category={category}, Intent={intent}, Confidence={confidence:.2f}")
        
        return ContextAnalysisResponse(**evaluation_data)
        
    except Exception as e:
        logger.error(f"❌ Error in context analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Context analysis failed: {str(e)}")

@app.post("/intelligent-search", response_model=IntelligentSearchResponse)
async def intelligent_search(request: IntelligentSearchRequest):
    """
    Perform intelligent multi-source search.
    
    Uses context-aware routing to search:
    - Retirement database (via search service)
    - UAT Azure DevOps work items
    - Technical Feedback Azure DevOps work items
    
    Results are ranked using semantic similarity and context relevance.
    """
    if matcher is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"🎯 Starting intelligent search for: {request.title[:50]}...")
        
        # Progress callback for logging
        def log_progress(step: int, total: int, percent: int, message: str):
            logger.info(f"📊 [{step}/{total}] {percent}% - {message}")
        
        results = matcher.intelligent_search_all_sources(
            request.title,
            request.description,
            request.impact or "",
            progress_callback=log_progress,
            skip_evaluation=request.skip_evaluation
        )
        
        total = results['results']['total_matches']
        logger.info(f"✅ Search complete: {total} matches found")
        
        return IntelligentSearchResponse(**results)
        
    except Exception as e:
        logger.error(f"❌ Error in intelligent search: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/continue-search", response_model=IntelligentSearchResponse)
async def continue_search(request: ContinueSearchRequest):
    """
    Continue search after human evaluation approval.
    
    Takes approved context analysis and proceeds with targeted search
    using the validated context understanding.
    """
    if matcher is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        evaluation_data = request.evaluation_data
        original = evaluation_data['original_issue']
        
        logger.info(f"▶️  Continuing approved search for: {original['title'][:50]}...")
        
        # Progress callback for logging
        def log_progress(step: int, total: int, percent: int, message: str):
            logger.info(f"📊 [{step}/{total}] {percent}% - {message}")
        
        results = matcher.continue_intelligent_search_after_approval(
            evaluation_data,
            progress_callback=log_progress
        )
        
        total = results['results']['total_matches']
        logger.info(f"✅ Approved search complete: {total} matches found")
        
        return IntelligentSearchResponse(**results)
        
    except Exception as e:
        logger.error(f"❌ Error in approved search: {e}")
        raise HTTPException(status_code=500, detail=f"Approved search failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("Enhanced Matching Service - Starting")
    print("="*80)
    print(f"Port: 8003")
    print(f"Features: AI Analysis, Context Evaluation, Intelligent Search")
    print(f"Azure DevOps: UAT + Technical Feedback integration")
    print("="*80)
    
    uvicorn.run(app, host="0.0.0.0", port=8003)
