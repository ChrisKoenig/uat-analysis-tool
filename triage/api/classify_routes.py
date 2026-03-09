"""
Classify API Routes
====================

Standalone classification endpoints — decoupled from ADO and Cosmos.
These accept raw text (title + description) and return AI classification
results without creating any database records or touching ADO.

Purpose:
    - External callers wanting classification only
    - Quick ICA form in the React UI
    - Future: Copilot API plugin surface

Endpoints:
    POST /classify           — Classify a single item
    POST /classify/batch     — Classify multiple items
    GET  /classify/status    — AI engine availability
    GET  /classify/categories — List all known categories
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("triage.api.classify")

# ---------------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    """Raw text input for classification — no ADO coupling."""
    title: str = Field(..., description="Item title or summary", min_length=1)
    description: str = Field("", description="Detailed description or body text")
    impact: str = Field("", description="Business impact statement (optional)")
    include_pattern_details: bool = Field(
        False,
        description="Include full pattern matching evidence in response"
    )


class ClassifyResult(BaseModel):
    """Classification output."""
    category: str
    intent: str
    business_impact: str
    confidence: float
    reasoning: Any  # str from LLM, dict from patterns
    source: str  # "llm", "pattern", or "hybrid"
    agreement: bool
    ai_available: bool
    ai_error: Optional[str] = None
    # Enrichments
    urgency_level: Optional[str] = None
    technical_complexity: Optional[str] = None
    context_summary: Optional[str] = None
    semantic_keywords: Optional[List[str]] = None
    key_concepts: Optional[List[str]] = None
    domain_entities: Optional[Dict[str, List[str]]] = None
    # Optional full pattern evidence
    pattern_details: Optional[Dict[str, Any]] = None
    # Timing
    elapsed_ms: int = 0


class ClassifyBatchRequest(BaseModel):
    """Batch classification — up to 20 items at a time."""
    items: List[ClassifyRequest] = Field(
        ...,
        description="List of items to classify",
        min_length=1,
        max_length=20,
    )


class ClassifyBatchResponse(BaseModel):
    """Batch classification results."""
    results: List[ClassifyResult]
    total: int
    elapsed_ms: int


class ClassifyStatusResponse(BaseModel):
    """AI engine availability."""
    available: bool
    ai_available: bool
    mode: str  # "hybrid", "pattern_only"
    details: Optional[Dict[str, Any]] = None


class CategoryInfo(BaseModel):
    """Category metadata."""
    name: str
    display_name: str
    description: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/classify", tags=["classify"])

# Lazy-loaded analyzer singleton
_analyzer = None


def _get_analyzer():
    """Get or create the hybrid analyzer singleton."""
    global _analyzer
    if _analyzer is None:
        try:
            import sys
            import os
            # Ensure root project is on sys.path so shared modules resolve
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            from services.hybrid_context_analyzer import HybridContextAnalyzer
            _analyzer = HybridContextAnalyzer(use_ai=True)
            logger.info("Hybrid analyzer initialized for classify routes")
        except Exception as e:
            logger.error(f"Failed to init hybrid analyzer: {e}")
            raise HTTPException(500, f"Analysis engine unavailable: {e}")
    return _analyzer


def _enum_val(v):
    """Safely extract .value from an enum, or return as-is."""
    return v.value if hasattr(v, "value") else v


def _result_to_response(result, include_pattern: bool, elapsed_ms: int) -> ClassifyResult:
    """Convert HybridAnalysisResult → ClassifyResult."""
    resp = ClassifyResult(
        category=_enum_val(result.category),
        intent=_enum_val(result.intent),
        business_impact=_enum_val(result.business_impact) if result.business_impact else "unknown",
        confidence=result.confidence,
        reasoning=result.reasoning,
        source=result.source,
        agreement=result.agreement,
        ai_available=result.ai_available,
        ai_error=result.ai_error,
        urgency_level=result.urgency_level,
        technical_complexity=result.technical_complexity,
        context_summary=result.context_summary,
        semantic_keywords=result.semantic_keywords,
        key_concepts=result.key_concepts,
        domain_entities=result.domain_entities,
        elapsed_ms=elapsed_ms,
    )
    if include_pattern:
        resp.pattern_details = {
            "pattern_category": _enum_val(result.pattern_category),
            "pattern_intent": _enum_val(result.pattern_intent),
            "pattern_confidence": result.pattern_confidence,
            "pattern_features": result.pattern_features,
            "pattern_reasoning": result.pattern_reasoning,
        }
    return resp


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ClassifyResult, summary="Classify a single item")
def classify_item(req: ClassifyRequest):
    """
    Classify raw text using the hybrid AI + pattern matching engine.

    This is a **stateless** operation — no ADO lookups, no Cosmos writes.
    Pass a title and optional description/impact to get instant classification.

    Returns category, intent, confidence, reasoning, and enrichments.
    """
    analyzer = _get_analyzer()
    t0 = time.perf_counter()

    try:
        result = analyzer.analyze(
            title=req.title,
            description=req.description,
            impact=req.impact,
            search_similar=False,
        )
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(500, f"Classification failed: {e}")

    elapsed = int((time.perf_counter() - t0) * 1000)
    return _result_to_response(result, req.include_pattern_details, elapsed)


@router.post("/batch", response_model=ClassifyBatchResponse, summary="Batch classify")
def classify_batch(req: ClassifyBatchRequest):
    """
    Classify up to 20 items in a single request.

    Each item is classified independently using the same hybrid engine.
    """
    analyzer = _get_analyzer()
    t0 = time.perf_counter()
    results = []

    for item in req.items:
        item_t0 = time.perf_counter()
        try:
            r = analyzer.analyze(
                title=item.title,
                description=item.description,
                impact=item.impact,
                search_similar=False,
            )
            item_elapsed = int((time.perf_counter() - item_t0) * 1000)
            results.append(_result_to_response(r, item.include_pattern_details, item_elapsed))
        except Exception as e:
            logger.error(f"Batch item failed: {e}")
            results.append(ClassifyResult(
                category="error",
                intent="error",
                business_impact="unknown",
                confidence=0.0,
                reasoning=f"Classification failed: {e}",
                source="error",
                agreement=False,
                ai_available=False,
                ai_error=str(e),
                elapsed_ms=int((time.perf_counter() - item_t0) * 1000),
            ))

    total_elapsed = int((time.perf_counter() - t0) * 1000)
    return ClassifyBatchResponse(
        results=results,
        total=len(results),
        elapsed_ms=total_elapsed,
    )


@router.get("/status", response_model=ClassifyStatusResponse, summary="AI engine status")
def classify_status():
    """Check whether the AI classification engine is available."""
    try:
        analyzer = _get_analyzer()
        ai_status = analyzer.get_ai_status()
        return ClassifyStatusResponse(
            available=True,
            ai_available=ai_status.get("enabled", False),
            mode="hybrid" if ai_status.get("enabled") else "pattern_only",
            details=ai_status,
        )
    except Exception as e:
        return ClassifyStatusResponse(
            available=False,
            ai_available=False,
            mode="unavailable",
            details={"error": str(e)},
        )


@router.get("/categories", response_model=List[CategoryInfo], summary="List categories")
def list_categories():
    """Return all known issue categories with display names and descriptions."""
    # These map to IssueCategory enum values in intelligent_context_analyzer.py
    categories = [
        CategoryInfo(name="technical_support", display_name="Technical Support",
                     description="Customer needs technical help with a product or service"),
        CategoryInfo(name="feature_request", display_name="Feature Request",
                     description="Request for a new feature or enhancement"),
        CategoryInfo(name="service_availability", display_name="Service Availability",
                     description="Question about regional or service availability"),
        CategoryInfo(name="capacity_management", display_name="Capacity Management",
                     description="Resource capacity planning or scaling request"),
        CategoryInfo(name="cost_billing", display_name="Cost & Billing",
                     description="Cost optimization, billing questions, or pricing inquiries"),
        CategoryInfo(name="training_documentation", display_name="Training & Documentation",
                     description="Request for training materials, demos, or documentation"),
        CategoryInfo(name="seeking_guidance", display_name="Seeking Guidance",
                     description="General guidance or best practices request"),
        CategoryInfo(name="product_retirement", display_name="Product Retirement",
                     description="Questions about deprecated or retiring products"),
        CategoryInfo(name="security_compliance", display_name="Security & Compliance",
                     description="Security, privacy, or compliance related inquiries"),
        CategoryInfo(name="migration", display_name="Migration",
                     description="Workload migration planning or assistance"),
        CategoryInfo(name="performance", display_name="Performance",
                     description="Performance troubleshooting or optimization"),
    ]
    return categories
