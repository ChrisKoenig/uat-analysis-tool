"""
Field Portal API Routes — 9-Step Submission Flow

Each endpoint is a discrete step in the wizard. The React UI calls them
sequentially; session state (in-memory via session_manager.py) carries
data between steps keyed by session_id.

Step Map:
  POST /submit                  → Steps 1-2  (create session, quality review)
  POST /analyze/{sid}           → Step 3     (hybrid AI + pattern analysis)
  GET  /analysis-detail/{sid}   → Step 3b    (expanded detail view)
  POST /correct                 → Step 4     (approve / correct / reanalyze)
  POST /search/{sid}            → Step 5     (Learn docs, TFT features, guidance)
  POST /features/toggle         → Step 5b    (select/deselect TFT feature)
  POST /uat-input               → Step 6     (save Opportunity & Milestone IDs)
  POST /related-uats/{sid}      → Step 7     (search similar UATs in ADO)
  POST /uats/toggle             → Step 8     (select/deselect related UATs)
  POST /create-uat              → Step 9     (create work item in ADO)

Heavy lifting is delegated to:
  - HybridContextAnalyzer (AI + pattern matching, imported from project root)
  - AzureDevOpsClient     (work item creation & TFT feature search)
  - AzureDevOpsSearcher   (UAT similarity search)
  - Microservice gateway   (:8000) as fallback for analysis & search
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException

# ── Add project root to path so we can import ADO integration directly ──
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from .models import (
    IssueSubmission, QualityReviewResponse, QualityIssue,
    AnalysisResponse, ContextAnalysis, DomainEntities,
    CorrectionRequest, CorrectionResponse,
    SearchResponse, LearnDoc, TFTFeature, CategoryGuidance,
    FeatureSelectionRequest, FeatureSelectionResponse,
    UATInputRequest,
    RelatedUATsResponse, RelatedUAT,
    UATSelectionRequest, UATSelectionResponse,
    UATCreateRequest, UATCreatedResponse, LinkedUAT,
    SessionState, FlowStep, HealthResponse,
)
from .session_manager import get_session_manager
from .gateway_client import get_gateway, GatewayError
from .guidance import get_category_guidance
from .cosmos_client import (
    store_field_portal_evaluation,
    store_correction,
)
from .config import (
    QUALITY_BLOCK_THRESHOLD, QUALITY_WARN_THRESHOLD,
    UAT_SEARCH_DAYS, UAT_MAX_SELECTED, TFT_SIMILARITY_THRESHOLD,
)

logger = logging.getLogger("field-portal.routes")

router = APIRouter(prefix="/api/field", tags=["Field Submission Flow"])

# ── Flow-path routing sets ──
DEFLECT_CATEGORIES = {
    "technical_support", "cost_billing", "aoai_capacity",
    "capacity", "support", "support_escalation",
}
FEATURE_SEARCH_CATEGORIES = {"feature_request", "service_availability"}


# ============================================================================
# Helpers
# ============================================================================

# ── Cached ADO clients (avoid re-authentication on every request) ──
_ado_client = None
_ado_searcher = None
_hybrid_analyzer = None
_fallback_ica = None

def _get_ado_client():
    """Get a cached AzureDevOpsClient singleton."""
    global _ado_client
    if _ado_client is None:
        from ado_integration import AzureDevOpsClient
        _ado_client = AzureDevOpsClient()
    return _ado_client

def _get_ado_searcher():
    """Get a cached AzureDevOpsSearcher singleton."""
    global _ado_searcher
    if _ado_searcher is None:
        from enhanced_matching import AzureDevOpsSearcher
        _ado_searcher = AzureDevOpsSearcher()
    return _ado_searcher


def _require_session(session_id: str) -> Dict[str, Any]:
    """Get session or 404."""
    entry = get_session_manager().get_session(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or expired")
    return entry


def _get_state(session_id: str) -> SessionState:
    state = get_session_manager().get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or expired")
    return state


# ── Well-known Microsoft product → Learn URL map ──
# Used by _generate_learn_docs when domain_entities.azure_services is empty
# to extract service names directly from the submission title/description.
_KNOWN_LEARN_PRODUCTS: Dict[str, tuple] = {
    # key: lowercase token → (Display Name, Learn URL)
    "entra": ("Microsoft Entra", "https://learn.microsoft.com/entra/"),
    "intune": ("Microsoft Intune", "https://learn.microsoft.com/mem/intune/"),
    "sentinel": ("Microsoft Sentinel", "https://learn.microsoft.com/azure/sentinel/"),
    "defender": ("Microsoft Defender", "https://learn.microsoft.com/microsoft-365/security/defender/"),
    "purview": ("Microsoft Purview", "https://learn.microsoft.com/purview/"),
    "fabric": ("Microsoft Fabric", "https://learn.microsoft.com/fabric/"),
    "copilot": ("Microsoft Copilot", "https://learn.microsoft.com/copilot/"),
    "teams": ("Microsoft Teams", "https://learn.microsoft.com/microsoftteams/"),
    "sharepoint": ("SharePoint", "https://learn.microsoft.com/sharepoint/"),
    "power bi": ("Power BI", "https://learn.microsoft.com/power-bi/"),
    "power automate": ("Power Automate", "https://learn.microsoft.com/power-automate/"),
    "power apps": ("Power Apps", "https://learn.microsoft.com/power-apps/"),
    "synapse": ("Azure Synapse Analytics", "https://learn.microsoft.com/azure/synapse-analytics/"),
    "databricks": ("Azure Databricks", "https://learn.microsoft.com/azure/databricks/"),
    "openai": ("Azure OpenAI", "https://learn.microsoft.com/azure/ai-services/openai/"),
    "virtual desktop": ("Azure Virtual Desktop", "https://learn.microsoft.com/azure/virtual-desktop/"),
    "avd": ("Azure Virtual Desktop", "https://learn.microsoft.com/azure/virtual-desktop/"),
    "cosmos": ("Azure Cosmos DB", "https://learn.microsoft.com/azure/cosmos-db/"),
    "kubernetes": ("Azure Kubernetes Service", "https://learn.microsoft.com/azure/aks/"),
    "aks": ("Azure Kubernetes Service", "https://learn.microsoft.com/azure/aks/"),
    "devops": ("Azure DevOps", "https://learn.microsoft.com/azure/devops/"),
    "sql": ("Azure SQL", "https://learn.microsoft.com/azure/azure-sql/"),
    "functions": ("Azure Functions", "https://learn.microsoft.com/azure/azure-functions/"),
    "storage": ("Azure Storage", "https://learn.microsoft.com/azure/storage/"),
    "monitor": ("Azure Monitor", "https://learn.microsoft.com/azure/azure-monitor/"),
    "key vault": ("Azure Key Vault", "https://learn.microsoft.com/azure/key-vault/"),
    "app service": ("Azure App Service", "https://learn.microsoft.com/azure/app-service/"),
    "logic apps": ("Azure Logic Apps", "https://learn.microsoft.com/azure/logic-apps/"),
    "event grid": ("Azure Event Grid", "https://learn.microsoft.com/azure/event-grid/"),
    "service bus": ("Azure Service Bus", "https://learn.microsoft.com/azure/service-bus-messaging/"),
    "private access": ("Microsoft Entra Private Access", "https://learn.microsoft.com/entra/global-secure-access/concept-private-access"),
    "global secure access": ("Microsoft Global Secure Access", "https://learn.microsoft.com/entra/global-secure-access/"),
}


def _extract_services_from_text(text: str) -> List[tuple]:
    """Extract known Microsoft products/services from free text.

    Returns list of (display_name, learn_url) tuples, deduped by URL.
    """
    text_lower = text.lower()
    seen_urls: set = set()
    results: list = []
    # Sort by longest key first so "private access" matches before "access"
    for key in sorted(_KNOWN_LEARN_PRODUCTS, key=len, reverse=True):
        if key in text_lower and _KNOWN_LEARN_PRODUCTS[key][1] not in seen_urls:
            display, url = _KNOWN_LEARN_PRODUCTS[key]
            seen_urls.add(url)
            results.append((display, url))
    return results


def _generate_learn_docs(title: str, description: str, domain_entities: dict, category: str) -> List[LearnDoc]:
    """
    Generate curated Microsoft Learn documentation links from domain entities.

    The old system (app.py) always produced Learn links for every category —
    including feature_request — by constructing URLs from the detected Azure
    services.  This replicates that behaviour so the Search Results page
    never shows "No Learn articles matched" when we already know the relevant
    services.
    """
    docs: List[LearnDoc] = []
    services = domain_entities.get("azure_services", [])
    technologies = domain_entities.get("technologies", [])

    # 1. General search link from title
    search_terms = title.strip()
    if search_terms:
        docs.append(LearnDoc(
            title=f"Search Microsoft Learn: {search_terms[:80]}",
            url=f"https://learn.microsoft.com/en-us/search/?terms={search_terms.replace(' ', '+')}",
            description=f"Search Microsoft Learn for: {search_terms}",
            score=0.9,
        ))

    # 2. Per-service documentation links —
    #    Prefer azure_services from domain_entities; fall back to extracting
    #    known product names directly from the title + description text.
    if services:
        for idx, service in enumerate(services[:3]):
            service_lower = service.lower().replace(" ", "-")
            docs.append(LearnDoc(
                title=f"{service} Documentation",
                url=f"https://learn.microsoft.com/en-us/azure/{service_lower}/",
                description=f"Official Microsoft Learn documentation for {service}",
                score=0.8 - (idx * 0.1),
            ))
    else:
        # Fallback: mine services from the raw title + description text
        combined_text = f"{title} {description}"
        extracted = _extract_services_from_text(combined_text)
        for idx, (display_name, learn_url) in enumerate(extracted[:3]):
            docs.append(LearnDoc(
                title=f"{display_name} Documentation",
                url=learn_url,
                description=f"Official Microsoft Learn documentation for {display_name}",
                score=0.8 - (idx * 0.1),
            ))

    # 3. Region / availability docs if relevant
    regions = domain_entities.get("regions", [])
    if regions and category == "service_availability":
        docs.append(LearnDoc(
            title="Azure Regions and Availability Zones",
            url="https://learn.microsoft.com/en-us/azure/reliability/availability-zones-overview",
            description="Learn about Azure regions, availability zones, and service availability",
            score=0.85,
        ))

    # 4. Capacity docs if relevant
    if category == "capacity":
        docs.append(LearnDoc(
            title="Azure Capacity Planning",
            url="https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/considerations/capacity",
            description="Guidance on Azure capacity planning and quota management",
            score=0.85,
        ))

    return docs


def _local_pattern_analysis(title: str, description: str, impact: str = "") -> Dict[str, Any]:
    """
    Run the HybridContextAnalyzer directly (pattern + LLM + vectors + corrections).
    Falls back to IntelligentContextAnalyzer (pattern-only) if hybrid init fails.
    No gateway or microservices required.
    Returns a dict matching the gateway's analyze-context response shape.
    """
    # Try the full hybrid analyzer first (same engine the old system uses)
    try:
        from hybrid_context_analyzer import HybridContextAnalyzer
        global _hybrid_analyzer
        if _hybrid_analyzer is None:
            _hybrid_analyzer = HybridContextAnalyzer(use_ai=True)
        # If cached analyzer has AI disabled from a past init failure, retry init
        elif not _hybrid_analyzer.use_ai and _hybrid_analyzer._init_error:
            logger.info(f"Retrying AI init (previous failure: {_hybrid_analyzer._init_error})")
            _hybrid_analyzer = HybridContextAnalyzer(use_ai=True)
        
        result = _hybrid_analyzer.analyze(title, description, impact)
        
        # Convert to gateway response shape
        cat = result.category.value if hasattr(result.category, 'value') else str(result.category)
        intent = result.intent.value if hasattr(result.intent, 'value') else str(result.intent)

        cat_display_map = {
            "technical_support": "Technical Support",
            "feature_request": "Feature Request",
            "cost_billing": "Cost & Billing",
            "compliance_security": "Compliance & Security",
            "training_enablement": "Training & Enablement",
            "service_health": "Service Health",
            "migration": "Migration",
            "performance": "Performance",
            "capacity": "Capacity",
            "aoai_capacity": "Azure OpenAI Capacity",
            "general": "General",
        }

        return {
            "context_analysis": {
                "category": cat,
                "category_display": cat_display_map.get(cat, cat.replace("_", " ").title()),
                "intent": intent,
                "intent_display": intent.replace("_", " ").title(),
                "confidence": result.confidence,
                "business_impact": result.business_impact,
                "business_impact_display": result.business_impact.replace("_", " ").title() if result.business_impact else "",
                "technical_complexity": result.technical_complexity,
                "urgency_level": result.urgency_level,
                "key_concepts": result.key_concepts,
                "semantic_keywords": result.semantic_keywords,
                "domain_entities": result.domain_entities if isinstance(result.domain_entities, dict) else {"azure_services": [], "technologies": [], "regions": []},
                "context_summary": result.context_summary,
                "reasoning": result.reasoning if result.reasoning else "",
                "pattern_reasoning": result.pattern_reasoning if hasattr(result, 'pattern_reasoning') else None,
                "source": result.source if hasattr(result, 'source') else "hybrid (direct)",
                "ai_available": result.ai_available if hasattr(result, 'ai_available') else True,
                "ai_error": result.ai_error if hasattr(result, 'ai_error') else None,
            }
        }
    except Exception as e:
        logger.warning(f"Hybrid analyzer failed, falling back to pattern matching: {e}")

    # Fallback: pattern matching only
    try:
        from intelligent_context_analyzer import IntelligentContextAnalyzer
        global _fallback_ica
        if _fallback_ica is None:
            _fallback_ica = IntelligentContextAnalyzer()
        analyzer = _fallback_ica
        result = analyzer.analyze_context(title, description, impact)

        # Convert enum values to strings
        cat = result.category.value if hasattr(result.category, 'value') else str(result.category)
        intent = result.intent.value if hasattr(result.intent, 'value') else str(result.intent)

        # Map category to display name
        cat_display_map = {
            "technical_support": "Technical Support",
            "feature_request": "Feature Request",
            "cost_billing": "Cost & Billing",
            "compliance_security": "Compliance & Security",
            "training_enablement": "Training & Enablement",
            "service_health": "Service Health",
            "migration": "Migration",
            "performance": "Performance",
            "capacity": "Capacity",
            "aoai_capacity": "Azure OpenAI Capacity",
            "general": "General",
        }

        return {
            "context_analysis": {
                "category": cat,
                "category_display": cat_display_map.get(cat, cat.replace("_", " ").title()),
                "intent": intent,
                "intent_display": intent.replace("_", " ").title(),
                "confidence": result.confidence,
                "business_impact": result.business_impact,
                "business_impact_display": result.business_impact.replace("_", " ").title() if result.business_impact else "",
                "technical_complexity": result.technical_complexity,
                "urgency_level": result.urgency_level,
                "key_concepts": result.key_concepts,
                "semantic_keywords": result.semantic_keywords,
                "domain_entities": result.domain_entities,
                "context_summary": result.context_summary,
                "reasoning": str(result.reasoning) if result.reasoning else "",
                "source": "pattern_matching (local fallback)",
                "ai_available": False,
                "ai_error": "API Gateway unreachable — used local pattern matching",
            }
        }
    except Exception as e:
        logger.error(f"Local pattern analysis also failed: {e}")
        # Absolute last resort — return minimal generic result
        return {
            "context_analysis": {
                "category": "general",
                "category_display": "General",
                "intent": "general",
                "intent_display": "General",
                "confidence": 0.1,
                "business_impact": "unknown",
                "business_impact_display": "Unknown",
                "technical_complexity": "unknown",
                "urgency_level": "medium",
                "key_concepts": [],
                "semantic_keywords": [],
                "domain_entities": {"azure_services": [], "technologies": [], "regions": []},
                "context_summary": "Analysis unavailable — both gateway and local analyzer failed.",
                "reasoning": "",
                "source": "fallback_minimal",
                "ai_available": False,
                "ai_error": f"All analysis methods failed: {str(e)[:200]}",
            }
        }


# ============================================================================
# Step 1-2: Submit + Quality Review
# ============================================================================

@router.post("/submit", response_model=QualityReviewResponse,
             summary="Submit issue and get quality review",
             description="Step 1-2: Submit title/description/impact, receive quality score.")
async def submit_issue(submission: IssueSubmission):
    """
    Creates a session, calls Azure OpenAI to evaluate submission quality,
    and returns scoring results with dimension breakdowns.
    Falls back to the old rules engine if the AI call fails.
    """
    import time as _t
    _SUB = "[SUBMIT-DEBUG]"
    _t_total = _t.monotonic()
    logger.info(f"{_SUB} ===== submit_issue START =====")
    from .ai_quality_evaluator import evaluate_quality

    logger.info(f"{_SUB} Step 1: evaluate_quality...")
    _t1 = _t.monotonic()
    quality = await evaluate_quality(
        title=submission.title,
        description=submission.description,
        impact=submission.impact,
    )
    logger.info(f"{_SUB} Step 1 done in {(_t.monotonic()-_t1)*1000:.0f}ms — score={quality.get('completeness_score')}")
    logger.info(
        f"Quality evaluation: score={quality.get('completeness_score')} "
        f"ai={quality.get('ai_evaluation', False)}"
    )

    score = quality.get("completeness_score", 100)
    blocked = score < QUALITY_BLOCK_THRESHOLD
    needs_improvement = score < QUALITY_WARN_THRESHOLD

    # Create session
    sm = get_session_manager()
    state = sm.create_session(submission)
    sm.update_state(state.session_id, quality_score=score, current_step=FlowStep.quality_review)

    # Build typed issues list
    issues = []
    for raw in quality.get("issues", []):
        if isinstance(raw, dict):
            issues.append(QualityIssue(**raw))
        elif isinstance(raw, str):
            issues.append(QualityIssue(field="general", severity="warning", message=raw))

    # Build AI dimension breakdown (if available)
    dimensions = None
    if quality.get("dimensions"):
        from .models import QualityDimensions, DimensionScore
        dims = quality["dimensions"]
        dimensions = QualityDimensions(
            title_clarity=DimensionScore(**dims.get("title_clarity", {})),
            description_quality=DimensionScore(**dims.get("description_quality", {})),
            business_impact=DimensionScore(**dims.get("business_impact", {})),
            actionability=DimensionScore(**dims.get("actionability", {})),
        )

    logger.info(f"{_SUB} ===== submit_issue END — total {(_t.monotonic()-_t_total)*1000:.0f}ms =====")
    return QualityReviewResponse(
        session_id=state.session_id,
        score=score,
        is_complete=quality.get("is_complete", True),
        needs_improvement=needs_improvement,
        blocked=blocked,
        issues=issues,
        suggestions=quality.get("suggestions", []),
        garbage_detected=quality.get("garbage_detected", False),
        original_input=submission,
        ai_evaluation=quality.get("ai_evaluation", False),
        dimensions=dimensions,
    )


# ============================================================================
# Step 3: Context Analysis
# ============================================================================

@router.post("/analyze/{session_id}", response_model=AnalysisResponse,
             summary="Run AI context analysis",
             description="Step 3: Run hybrid analysis (pattern + LLM + vectors + corrections).")
async def analyze_context(session_id: str):
    """
    Runs the HybridContextAnalyzer directly (same engine as old system).
    Falls back to gateway if direct analysis fails.
    Stores full results in session for later steps.
    """
    import time as _t
    _ANL = "[ANALYZE-DEBUG]"
    _t_total = _t.monotonic()
    logger.info(f"{_ANL} ===== analyze_context START session={session_id} =====")

    state = _get_state(session_id)
    if state.original_input is None:
        raise HTTPException(400, "No submission data in session — call /submit first")

    inp = state.original_input

    # Primary path: run analysis engine directly (no gateway/microservice needed)
    logger.info(f"{_ANL} Step 1: _local_pattern_analysis...")
    _t1 = _t.monotonic()
    raw = _local_pattern_analysis(inp.title, inp.description, inp.impact)
    logger.info(f"{_ANL} Step 1 done in {(_t.monotonic()-_t1)*1000:.0f}ms")
    source = raw.get("context_analysis", {}).get("source", "")

    # If direct analysis gave only a minimal fallback, try gateway as backup
    if source == "fallback_minimal":
        logger.info(f"{_ANL} Step 2: source=fallback_minimal — trying gateway backup...")
        _t2 = _t.monotonic()
        try:
            gw = get_gateway()
            raw = await gw.analyze_context(
                title=inp.title,
                description=inp.description,
                impact=inp.impact,
            )
            logger.info(f"{_ANL} Step 2 done in {(_t.monotonic()-_t2)*1000:.0f}ms — gateway fallback succeeded")
        except GatewayError as e:
            logger.warning(f"{_ANL} Step 2 failed in {(_t.monotonic()-_t2)*1000:.0f}ms — Gateway unavailable: {e}")
            # raw already has the minimal fallback, keep it
    else:
        logger.info(f"{_ANL} Step 2: source={source} — no gateway fallback needed")

    # Extract context_analysis from response
    ctx_raw = raw.get("context_analysis", raw)

    # Build domain entities
    de_raw = ctx_raw.get("domain_entities", {})
    domain_entities = DomainEntities(
        azure_services=de_raw.get("azure_services", []),
        technologies=de_raw.get("technologies", []),
        regions=de_raw.get("regions", []),
    )

    analysis = ContextAnalysis(
        category=ctx_raw.get("category", "general"),
        category_display=ctx_raw.get("category_display", ""),
        intent=ctx_raw.get("intent", "general"),
        intent_display=ctx_raw.get("intent_display", ""),
        confidence=ctx_raw.get("confidence", 0.0),
        business_impact=ctx_raw.get("business_impact", ""),
        business_impact_display=ctx_raw.get("business_impact_display", ""),
        technical_complexity=ctx_raw.get("technical_complexity", ""),
        urgency_level=ctx_raw.get("urgency_level", ""),
        key_concepts=ctx_raw.get("key_concepts", []),
        semantic_keywords=ctx_raw.get("semantic_keywords", []),
        domain_entities=domain_entities,
        context_summary=ctx_raw.get("context_summary", ""),
        reasoning=ctx_raw.get("reasoning", ""),
        source=ctx_raw.get("source", ""),
        ai_available=ctx_raw.get("ai_available", True),
        ai_error=ctx_raw.get("ai_error"),
    )

    # Update session
    sm = get_session_manager()
    sm.update_state(session_id,
                    analysis=analysis.model_dump(),
                    current_step=FlowStep.analysis)
    sm.set_extra(session_id, "raw_analysis", raw)

    logger.info(f"{_ANL} ===== analyze_context END — total {(_t.monotonic()-_t_total)*1000:.0f}ms, category={analysis.category} =====")

    return AnalysisResponse(
        session_id=session_id,
        original_input=inp,
        analysis=analysis,
    )


# ============================================================================
# Step 3b: Analysis Detail (full raw data for the detail view)
# ============================================================================

@router.get("/analysis-detail/{session_id}",
            summary="Get full analysis detail",
            description="Returns the complete raw analysis data for the detailed review page.")
async def get_analysis_detail(session_id: str):
    """
    Returns the complete analysis including raw gateway response,
    pattern analysis steps, domain entities, search strategy, etc.
    This powers the detailed analysis review page.
    """
    state = _get_state(session_id)
    sm = get_session_manager()

    if state.analysis is None:
        raise HTTPException(400, "No analysis in session — call /analyze first")

    raw = sm.get_extra(session_id, "raw_analysis") or {}
    ctx_raw = raw.get("context_analysis", raw)
    analysis_obj = state.analysis

    # Extract reasoning — may be a string (LLM) or dict (pattern analyzer)
    reasoning_raw = analysis_obj.reasoning if analysis_obj else ""
    pattern_steps = []
    reasoning_text = ""
    data_sources = []
    confidence_breakdown = []
    final_analysis = {}

    if isinstance(reasoning_raw, dict):
        pattern_steps = reasoning_raw.get("step_by_step", [])
        data_sources = reasoning_raw.get("data_sources_used", [])
        confidence_breakdown = reasoning_raw.get("confidence_breakdown", [])
        final_analysis = reasoning_raw.get("final_analysis", {})
        reasoning_text = final_analysis.get("category_reason", "")
    elif isinstance(reasoning_raw, str):
        reasoning_text = reasoning_raw

    # Also check pattern_reasoning in raw (hybrid analyzer stores it separately)
    pattern_reasoning = ctx_raw.get("pattern_reasoning", {})
    if isinstance(pattern_reasoning, dict) and not pattern_steps:
        pattern_steps = pattern_reasoning.get("step_by_step", [])
        data_sources = pattern_reasoning.get("data_sources_used", data_sources)
        confidence_breakdown = pattern_reasoning.get("confidence_breakdown", confidence_breakdown)
        final_analysis = pattern_reasoning.get("final_analysis", final_analysis)

    # Search strategy — check both keys the codebase may use
    search_strategy = ctx_raw.get("recommended_search_strategy",
                                  ctx_raw.get("search_strategy", {}))

    # Build the rich detail response
    detail = {
        "session_id": session_id,
        "original_input": state.original_input.model_dump() if state.original_input else {},

        # High-level classification
        "analysis": analysis_obj.model_dump() if analysis_obj else {},

        # Analysis method info
        "analysis_method": {
            "source": analysis_obj.source if analysis_obj else "",
            "ai_available": analysis_obj.ai_available if analysis_obj else False,
            "ai_error": analysis_obj.ai_error if analysis_obj else None,
            "confidence": analysis_obj.confidence if analysis_obj else 0,
            "model": ctx_raw.get("model", ""),
            "analysis_time_ms": ctx_raw.get("analysis_time_ms", 0),
        },

        # Context summary
        "context_summary": analysis_obj.context_summary if analysis_obj else "",

        # Reasoning (string for display — empty when same as context_summary to avoid duplication)
        "reasoning": reasoning_text if reasoning_text != (analysis_obj.context_summary if analysis_obj else "") else "",

        # Pattern analysis steps (step-by-step list)
        "pattern_analysis_steps": pattern_steps,

        # Data sources consulted
        "data_sources": data_sources,

        # Confidence breakdown
        "confidence_breakdown": confidence_breakdown,

        # Final analysis reasoning
        "final_analysis": final_analysis,

        # Domain entities (expanded)
        "domain_entities": {
            "azure_services": ctx_raw.get("domain_entities", {}).get("azure_services", []),
            "technologies": ctx_raw.get("domain_entities", {}).get("technologies", []),
            "technical_areas": ctx_raw.get("domain_entities", {}).get("technical_areas", []),
            "business_domains": ctx_raw.get("domain_entities", {}).get("business_domains", []),
            "compliance_frameworks": ctx_raw.get("domain_entities", {}).get("compliance_frameworks", []),
            "regions": ctx_raw.get("domain_entities", {}).get("regions", []),
            "discovered_services": ctx_raw.get("domain_entities", {}).get("discovered_services", []),
        },

        # Semantic keywords and key concepts
        "key_concepts": analysis_obj.key_concepts if analysis_obj else [],
        "semantic_keywords": analysis_obj.semantic_keywords if analysis_obj else [],

        # Search strategy recommendation
        "search_strategy": search_strategy,

        # Technical complexity / urgency breakdown
        "technical_complexity": analysis_obj.technical_complexity if analysis_obj else "",
        "urgency_level": analysis_obj.urgency_level if analysis_obj else "",

        # Raw entity extraction info
        "entity_count": ctx_raw.get("entity_count", 0),
        "extracted_entities": ctx_raw.get("extracted_entities", []),

        # Whether corrections were applied
        "corrections_applied": state.corrections_applied,
        "is_reanalyzed": state.is_reanalyzed,
    }

    return detail


# ============================================================================
# Step 4: Correction
# ============================================================================

@router.post("/correct", response_model=CorrectionResponse,
             summary="Submit classification corrections",
             description="Step 4: User corrects category/intent/impact. Optionally reanalyze.")
async def correct_classification(req: CorrectionRequest):
    """
    Handles user corrections to the AI classification.
    - 'approve': Accept as-is, proceed to search
    - 'reanalyze': Re-run analysis with correction hints
    - 'save_corrections': Save feedback for learning, proceed
    - 'reject': Discard and start over
    """
    state = _get_state(req.session_id)
    sm = get_session_manager()

    corrections: Dict[str, str] = {}
    if req.correct_category:
        corrections["category"] = req.correct_category
    if req.correct_intent:
        corrections["intent"] = req.correct_intent
    if req.correct_business_impact:
        corrections["business_impact"] = req.correct_business_impact
    if req.correct_technical_complexity:
        corrections["technical_complexity"] = req.correct_technical_complexity
    if req.correct_urgency_level:
        corrections["urgency_level"] = req.correct_urgency_level

    if req.action == "reject":
        sm.delete_session(req.session_id)
        return CorrectionResponse(
            session_id=req.session_id,
            action="reject",
            message="Session discarded. Start a new submission.",
        )

    if req.action == "approve":
        sm.update_state(req.session_id, current_step=FlowStep.search)
        return CorrectionResponse(
            session_id=req.session_id,
            action="approve",
            updated_analysis=state.analysis,
            message="Classification approved. Proceeding to search.",
        )

    if req.action == "save_corrections":
        # Save corrections to Cosmos DB for fine-tuning consumption
        original_analysis = (
            state.analysis if isinstance(state.analysis, dict)
            else (state.analysis.model_dump() if state.analysis else {})
        )
        original_title = (
            state.original_input.get("title", "") if isinstance(state.original_input, dict)
            else (state.original_input.title if state.original_input else "")
        )
        store_correction(
            work_item_id=state.work_item_id or 0,
            original_title=original_title,
            original_analysis=original_analysis,
            corrections=corrections,
            notes=req.correction_notes or "",
            source="field-portal",
        )
        # Also keep local backup (legacy)
        _save_correction_feedback(state, corrections, req.correction_notes)
        # Apply corrections to session state
        updated = _apply_corrections_to_analysis(state, corrections)
        sm.update_state(req.session_id,
                        analysis=updated.model_dump(),
                        corrections_applied=corrections,
                        current_step=FlowStep.search)
        return CorrectionResponse(
            session_id=req.session_id,
            action="save_corrections",
            updated_analysis=updated,
            corrections_applied=corrections,
            message="Corrections saved for learning. Proceeding to search.",
        )

    if req.action == "reanalyze":
        # Re-run analysis with correction hints in the description
        inp = state.original_input

        # Build enhanced description with correction context
        correction_context = []
        if req.correct_category:
            correction_context.append(f"[CORRECTION: Category should be {req.correct_category}]")
        if req.correct_intent:
            correction_context.append(f"[CORRECTION: Intent should be {req.correct_intent}]")
        if req.correction_notes:
            correction_context.append(f"[USER NOTE: {req.correction_notes}]")

        enhanced_desc = inp.description
        if correction_context:
            enhanced_desc += "\n\n" + "\n".join(correction_context)

        # Primary path: run analysis engine directly (no gateway needed)
        raw = _local_pattern_analysis(inp.title, enhanced_desc, inp.impact)
        source = raw.get("context_analysis", {}).get("source", "")

        # If direct analysis gave only a minimal fallback, try gateway as backup
        if source == "fallback_minimal":
            try:
                gw = get_gateway()
                raw = await gw.analyze_context(
                    title=inp.title,
                    description=enhanced_desc,
                    impact=inp.impact,
                )
                logger.info("Re-analysis succeeded via gateway fallback")
            except GatewayError as e:
                logger.warning(f"Gateway also unavailable for re-analysis: {e}")
                # raw already has the minimal fallback, keep it

        ctx_raw = raw.get("context_analysis", raw)
        de_raw = ctx_raw.get("domain_entities", {})

        # Resolve final values, applying user corrections on top of LLM output
        final_category = corrections.get("category", ctx_raw.get("category", "general"))
        final_intent = corrections.get("intent", ctx_raw.get("intent", "general"))
        final_impact = corrections.get("business_impact", ctx_raw.get("business_impact", ""))

        # Build display names that match the corrected values
        _cat_display_map = {
            "technical_support": "Technical Support",
            "feature_request": "Feature Request",
            "cost_billing": "Cost & Billing",
            "compliance_security": "Compliance & Security",
            "compliance_regulatory": "Compliance/Regulatory",
            "security_governance": "Security/Governance",
            "training_enablement": "Training & Enablement",
            "service_health": "Service Health",
            "service_availability": "Service Availability",
            "service_retirement": "Service Retirement",
            "retirements": "Retirements",
            "migration": "Migration",
            "migration_modernization": "Migration/Modernization",
            "performance": "Performance",
            "performance_optimization": "Performance Issue",
            "capacity": "Capacity",
            "aoai_capacity": "AOAI Capacity",
            "business_desk": "Business Desk",
            "roadmap": "Roadmap",
            "product_roadmap": "Product Roadmap",
            "support": "Support",
            "support_escalation": "Support Escalation",
            "data_sovereignty": "Data Sovereignty",
            "sustainability": "Sustainability",
            "integration_connectivity": "Integration Issue",
            "training_documentation": "Training/Documentation",
            "general": "General",
            "other": "Other",
        }
        final_cat_display = (
            _cat_display_map.get(final_category, final_category.replace("_", " ").title())
            if "category" in corrections
            else ctx_raw.get("category_display", final_category.replace("_", " ").title())
        )
        final_intent_display = (
            final_intent.replace("_", " ").title()
            if "intent" in corrections
            else ctx_raw.get("intent_display", final_intent.replace("_", " ").title())
        )
        final_impact_display = (
            final_impact.replace("_", " ").title() if final_impact else ""
        ) if "business_impact" in corrections else ctx_raw.get("business_impact_display", "")

        updated = ContextAnalysis(
            category=final_category,
            category_display=final_cat_display,
            intent=final_intent,
            intent_display=final_intent_display,
            confidence=ctx_raw.get("confidence", 0.0),
            business_impact=final_impact,
            business_impact_display=final_impact_display,
            technical_complexity=corrections.get("technical_complexity", ctx_raw.get("technical_complexity", "")),
            urgency_level=corrections.get("urgency_level", ctx_raw.get("urgency_level", "")),
            key_concepts=ctx_raw.get("key_concepts", []),
            semantic_keywords=ctx_raw.get("semantic_keywords", []),
            domain_entities=DomainEntities(
                azure_services=de_raw.get("azure_services", []),
                technologies=de_raw.get("technologies", []),
                regions=de_raw.get("regions", []),
            ),
            context_summary=ctx_raw.get("context_summary", ""),
            reasoning=ctx_raw.get("reasoning", ""),
            source=ctx_raw.get("source", ""),
            ai_available=ctx_raw.get("ai_available", True),
            ai_error=ctx_raw.get("ai_error"),
        )

        sm.update_state(req.session_id,
                        analysis=updated.model_dump(),
                        corrections_applied=corrections,
                        is_reanalyzed=True,
                        current_step=FlowStep.correction)
        sm.set_extra(req.session_id, "raw_analysis", raw)

        return CorrectionResponse(
            session_id=req.session_id,
            action="reanalyze",
            updated_analysis=updated,
            corrections_applied=corrections,
            message="Re-analysis complete with corrections applied.",
        )

    raise HTTPException(400, f"Unknown action: {req.action}")


def _apply_corrections_to_analysis(state: SessionState, corrections: Dict[str, str]) -> ContextAnalysis:
    """Apply user corrections to the existing analysis."""
    data = state.analysis.model_dump() if state.analysis else {}
    for key, val in corrections.items():
        if key in data:
            data[key] = val
    # Sync display fields to match corrected slug values
    if "category" in corrections:
        data["category_display"] = corrections["category"].replace("_", " ").title()
    if "intent" in corrections:
        data["intent_display"] = corrections["intent"].replace("_", " ").title()
    if "business_impact" in corrections:
        data["business_impact_display"] = corrections["business_impact"].replace("_", " ").title() if corrections["business_impact"] else ""
    return ContextAnalysis(**data)


def _save_correction_feedback(state: SessionState, corrections: Dict[str, str], notes: str):
    """Save correction feedback to corrections.json for learning (legacy backup).

    This is a best-effort local backup.  On App Service the filesystem is
    read-only so this will silently fail — the primary Cosmos DB write in
    store_correction() is what matters.
    """
    try:
        import json
        corrections_file = os.path.join(PROJECT_ROOT, "corrections.json")
        try:
            with open(corrections_file, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"corrections": []}

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "original_title": state.original_input.title if state.original_input else "",
            "original_category": state.analysis.category if state.analysis else "",
            "original_intent": state.analysis.intent if state.analysis else "",
            "corrections": corrections,
            "notes": notes,
            "source": "field-portal",
        }
        data.setdefault("corrections", []).append(entry)

        with open(corrections_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved correction feedback: {corrections}")
    except Exception as e:
        logger.warning(f"Could not save local correction backup: {e} (Cosmos DB is primary)")


def _build_evaluation_summary_html(
    analysis: Dict[str, Any],
    title: str,
    state: SessionState,
) -> str:
    """
    Generate an HTML summary of the field portal AI evaluation.

    This HTML is written to the ADO work item's Challenge Details field
    and also persisted in the Cosmos evaluation document. It mirrors the
    format used by the triage system's ``_generate_summary_html``.

    Args:
        analysis:  AI classification dict (category, intent, confidence, etc.)
        title:     Work item title
        state:     Session state (for corrections and features)

    Returns:
        HTML string suitable for ADO rich-text fields
    """
    category = analysis.get("category", "Unknown")
    intent = analysis.get("intent", "Unknown")
    confidence = analysis.get("confidence", 0)
    business_impact = analysis.get("business_impact", "")
    technical_complexity = analysis.get("technical_complexity", "")
    urgency_level = analysis.get("urgency_level", "")
    reasoning = analysis.get("reasoning", "")

    # Confidence as percentage
    conf_pct = f"{confidence:.0%}" if isinstance(confidence, float) else f"{confidence}%"

    sections = []

    # Classification summary
    sections.append(f"""
    <h3>AI Classification</h3>
    <table>
        <tr><td><b>Category:</b></td><td>{category.replace('_', ' ').title()}</td></tr>
        <tr><td><b>Intent:</b></td><td>{intent.replace('_', ' ').title()}</td></tr>
        <tr><td><b>Confidence:</b></td><td>{conf_pct}</td></tr>
        <tr><td><b>Business Impact:</b></td><td>{business_impact}</td></tr>
        <tr><td><b>Technical Complexity:</b></td><td>{technical_complexity}</td></tr>
        <tr><td><b>Urgency:</b></td><td>{urgency_level}</td></tr>
    </table>
    """)

    # Reasoning
    if reasoning:
        sections.append(f"""
        <h3>Classification Reasoning</h3>
        <p>{reasoning}</p>
        """)

    # Domain entities
    domain_entities = analysis.get("domain_entities", {})
    if domain_entities:
        services = domain_entities.get("azure_services", [])
        techs = domain_entities.get("technologies", [])
        if services or techs:
            sections.append(f"""
            <h3>Detected Entities</h3>
            <p><b>Azure Services:</b> {', '.join(services) if services else 'None'}</p>
            <p><b>Technologies:</b> {', '.join(techs) if techs else 'None'}</p>
            """)

    # Corrections
    if state.corrections_applied:
        rows = ""
        for field_name, new_val in state.corrections_applied.items():
            rows += f"<tr><td>{field_name}</td><td>{new_val}</td></tr>"
        sections.append(f"""
        <h3>User Corrections Applied</h3>
        <table border="1">
            <tr><th>Field</th><th>Corrected Value</th></tr>
            {rows}
        </table>
        """)

    # Guided override note
    if state.guided_override:
        category_label = analysis.get("category", "unknown").replace("_", " ").title()
        sections.append(f"""
        <h3>Deflection Override</h3>
        <p>The submitter was shown guidance for <b>{category_label}</b> and chose to create a UAT anyway.</p>
        """)

    # Metadata
    sections.append(f"""
    <h3>Evaluation Metadata</h3>
    <p><b>Source:</b> Field Portal (wizard submission)</p>
    <p><b>Date:</b> {datetime.utcnow().isoformat()}</p>
    """)

    body = "\n".join(sections)
    return f"""
    <div style="font-family: Segoe UI, sans-serif; font-size: 12px;">
        <h2>Field Portal Evaluation Summary</h2>
        {body}
    </div>
    """


# ============================================================================
# Step 5: Resource Search
# ============================================================================

@router.post("/search/{session_id}", response_model=SearchResponse,
             summary="Search for resources and guidance",
             description="Step 5: Search Learn docs, retirement info, capacity, TFT features.")
async def search_resources(session_id: str, deep_search: bool = False):
    """
    Runs resource search using the existing search microservice.
    Also checks for TFT features (if feature_request category) and
    returns category-specific guidance.
    """
    import time as _t
    _SRCH = "[SEARCH-DEBUG]"
    _t_total = _t.monotonic()
    logger.info(f"{_SRCH} ===== search_resources START session={session_id} =====")

    logger.info(f"{_SRCH} Step A: _get_state...")
    _ta = _t.monotonic()
    state = _get_state(session_id)
    logger.info(f"{_SRCH} Step A done in {(_t.monotonic()-_ta)*1000:.0f}ms")
    sm = get_session_manager()

    if state.analysis is None:
        raise HTTPException(400, "No analysis in session — call /analyze first")
    if state.original_input is None:
        raise HTTPException(400, "No submission data in session")

    logger.info(f"{_SRCH} Step B: extract analysis fields...")
    _tb = _t.monotonic()
    analysis = state.analysis if isinstance(state.analysis, dict) else state.analysis
    category = analysis.get("category", "general") if isinstance(analysis, dict) else getattr(analysis, "category", "general")
    intent = analysis.get("intent", "general") if isinstance(analysis, dict) else getattr(analysis, "intent", "general")

    if isinstance(analysis, dict):
        de = analysis.get("domain_entities", {})
    else:
        # ContextAnalysis model — extract domain_entities properly
        de_obj = getattr(analysis, "domain_entities", None)
        if de_obj is not None:
            de = de_obj.model_dump() if hasattr(de_obj, "model_dump") else (de_obj if isinstance(de_obj, dict) else {})
        else:
            de = {}

    inp = state.original_input if isinstance(state.original_input, dict) else state.original_input
    title = inp.get("title", "") if isinstance(inp, dict) else inp.title
    description = inp.get("description", "") if isinstance(inp, dict) else inp.description

    domain_entities = de if isinstance(de, dict) else {
        "azure_services": de.azure_services if hasattr(de, "azure_services") else [],
        "technologies": de.technologies if hasattr(de, "technologies") else [],
        "regions": de.regions if hasattr(de, "regions") else [],
    }
    logger.info(f"{_SRCH} Step B done in {(_t.monotonic()-_tb)*1000:.0f}ms — category={category}, intent={intent}")

    logger.info(f"{_SRCH} Step C: _generate_learn_docs...")
    _tc = _t.monotonic()
    learn_docs = _generate_learn_docs(title, description, domain_entities, category)
    logger.info(f"{_SRCH} Step C done in {(_t.monotonic()-_tc)*1000:.0f}ms — {len(learn_docs)} docs")
    search_metadata = {}

    # ── Determine flow path ──
    logger.info(f"{_SRCH} Step D: determine flow_path — category={category}")
    if category in DEFLECT_CATEGORIES:
        flow_path = "deflect"
    elif category in FEATURE_SEARCH_CATEGORIES:
        flow_path = "feature_search"
    else:
        flow_path = "create_uat"
    logger.info(f"{_SRCH} Step D done — flow_path={flow_path}")

    # ── TFT Feature search (feature_request only) ──
    tft_features: List[TFTFeature] = []
    tft_diag: Dict[str, Any] = {
        "searched": False,
        "category": category,
        "threshold": TFT_SIMILARITY_THRESHOLD,
        "azure_services": domain_entities.get("azure_services", []),
        "title_used": title,
    }
    _TFT = "[TFT-ROUTE-DEBUG]"
    logger.info(f"{_TFT} ===== TFT Feature Search START =====")
    logger.info(f"{_TFT} category={repr(category)}, threshold={TFT_SIMILARITY_THRESHOLD}")
    logger.info(f"{_TFT} domain_entities={domain_entities}")
    logger.info(f"{_TFT} title={repr(title[:100])}")
    if category in FEATURE_SEARCH_CATEGORIES:
        try:
            import time as _t
            t0 = _t.monotonic()
            logger.info(f"{_TFT} Step 1: Getting ADO client...")
            ado_client = _get_ado_client()
            tft_diag["searched"] = True
            logger.info(f"{_TFT} Step 2: Calling search_tft_features(title={repr(title[:60])}, threshold={TFT_SIMILARITY_THRESHOLD}, azure_services={domain_entities.get('azure_services', [])})")
            raw_features = ado_client.search_tft_features(
                title, description, threshold=TFT_SIMILARITY_THRESHOLD,
                azure_services=domain_entities.get("azure_services", [])
            )
            elapsed = round((_t.monotonic() - t0) * 1000)
            tft_diag["elapsed_ms"] = elapsed
            logger.info(f"{_TFT} Step 3: search_tft_features returned type={type(raw_features).__name__}, len={len(raw_features) if isinstance(raw_features, list) else 'N/A'}, elapsed={elapsed}ms")
            if isinstance(raw_features, list):
                tft_diag["raw_count"] = len(raw_features)
                if raw_features:
                    for i, f in enumerate(raw_features[:5]):
                        logger.info(f"{_TFT}   raw[{i}] id={f.get('id')} sim={f.get('similarity')} title={repr(f.get('title','')[:60])}")
                for f in raw_features:
                    tft_features.append(TFTFeature(
                        id=f.get("id", 0),
                        title=f.get("title", ""),
                        url=f.get("url", ""),
                        similarity=f.get("similarity", 0.0),
                        state=f.get("state", ""),
                        area_path=f.get("area_path", ""),
                    ))
                tft_diag["returned_count"] = len(tft_features)
                logger.info(f"{_TFT} Step 4: Converted {len(tft_features)} TFTFeature objects")
            elif isinstance(raw_features, dict) and "error" in raw_features:
                logger.warning(f"{_TFT} Step 3: Search returned error dict: {raw_features}")
                tft_diag["error"] = raw_features.get("message", str(raw_features))
                search_metadata["tft_error"] = tft_diag["error"]
            else:
                logger.warning(f"{_TFT} Step 3: Unexpected result type: {type(raw_features)}")
                tft_diag["error"] = f"Unexpected result type: {type(raw_features).__name__}"
            sm.set_extra(session_id, "tft_features_detail", [f.model_dump() for f in tft_features])
        except Exception as e:
            logger.error(f"{_TFT} EXCEPTION: {e}", exc_info=True)
            tft_diag["error"] = str(e)
            search_metadata["tft_error"] = str(e)
    else:
        tft_diag["skipped"] = f"category is '{category}', not in FEATURE_SEARCH_CATEGORIES"
        logger.info(f"{_TFT} Skipped: category={repr(category)} not in FEATURE_SEARCH_CATEGORIES")
    logger.info(f"{_TFT} ===== TFT Feature Search END — tft_diag={tft_diag} =====")
    search_metadata["tft_diagnostics"] = tft_diag

    # Category guidance
    logger.info(f"{_SRCH} Step F: get_category_guidance...")
    _tf = _t.monotonic()
    cat_guidance = get_category_guidance(category)
    logger.info(f"{_SRCH} Step F done in {(_t.monotonic()-_tf)*1000:.0f}ms — guidance={'present' if cat_guidance else 'none'}")

    # Update session
    logger.info(f"{_SRCH} Step G: update session state...")
    _tg = _t.monotonic()
    sm.update_state(session_id,
                    search_results=search_metadata,
                    current_step=FlowStep.search)
    logger.info(f"{_SRCH} Step G done in {(_t.monotonic()-_tg)*1000:.0f}ms")

    total_ms = (_t.monotonic() - _t_total) * 1000
    logger.info(f"{_SRCH} ===== search_resources END — total {total_ms:.0f}ms, flow_path={flow_path} =====")

    return SearchResponse(
        session_id=session_id,
        learn_docs=learn_docs,
        similar_products=[],
        regional_options=[],
        capacity_guidance=None,
        retirement_info=None,
        tft_features=tft_features,
        category_guidance=cat_guidance,
        search_metadata=search_metadata,
        flow_path=flow_path,
    )


# ============================================================================
# Step 5b: Toggle TFT Feature selection
# ============================================================================

@router.post("/features/toggle", response_model=FeatureSelectionResponse,
             summary="Toggle TFT feature selection",
             description="Add or remove a TFT feature from the selection list.")
async def toggle_feature_selection(req: FeatureSelectionRequest):
    state = _get_state(req.session_id)
    sm = get_session_manager()

    selected = list(state.selected_features)
    if req.feature_id in selected:
        selected.remove(req.feature_id)
        msg = f"Feature {req.feature_id} deselected"
    else:
        selected.append(req.feature_id)
        msg = f"Feature {req.feature_id} selected"

    sm.update_state(req.session_id, selected_features=selected)

    return FeatureSelectionResponse(
        session_id=req.session_id,
        selected_features=selected,
        message=msg,
    )


# ============================================================================
# Step 6: UAT Input (Opportunity / Milestone IDs)
# ============================================================================

@router.post("/uat-input", response_model=dict,
             summary="Save opportunity and milestone IDs",
             description="Step 6: Save opportunity/milestone IDs before UAT search.")
async def save_uat_input(req: UATInputRequest):
    _require_session(req.session_id)
    sm = get_session_manager()
    sm.update_state(req.session_id,
                    opportunity_id=req.opportunity_id,
                    milestone_id=req.milestone_id,
                    current_step=FlowStep.uat_input)

    return {"session_id": req.session_id, "message": "IDs saved", "next": "related-uats"}


# ============================================================================
# Step 7: Related UAT Search
# ============================================================================

@router.post("/related-uats/{session_id}", response_model=RelatedUATsResponse,
             summary="Search for similar UATs",
             description="Step 7: Search ADO for similar UATs from last 180 days.")
async def search_related_uats(session_id: str):
    state = _get_state(session_id)
    sm = get_session_manager()

    if state.original_input is None:
        raise HTTPException(400, "No submission data in session")

    inp = state.original_input if isinstance(state.original_input, dict) else state.original_input
    title = inp.get("title", "") if isinstance(inp, dict) else inp.title
    description = inp.get("description", "") if isinstance(inp, dict) else inp.description

    # ── FR-2020: Extract AI analysis from session (Step 3 / Step 4 corrections) ──
    # WHY: The AI analysis from Step 3 detects specific Azure services,
    # technologies, and semantic keywords. Passing these to the search produces
    # far better ADO Search API results than using the raw issue title alone,
    # because the search text matches the vocabulary actually used in UAT titles.
    ai_services: List[str] = []
    ai_keywords: List[str] = []
    ai_concepts: List[str] = []
    if state.analysis:
        a = state.analysis if isinstance(state.analysis, dict) else state.analysis.model_dump()
        de = a.get("domain_entities", {})
        if isinstance(de, dict):
            ai_services = de.get("azure_services", []) + de.get("technologies", [])
        else:
            ai_services = getattr(de, "azure_services", []) + getattr(de, "technologies", [])
        ai_keywords = a.get("semantic_keywords", [])
        ai_concepts = a.get("key_concepts", [])

    # Search via ADO directly (the gateway route proxies to enhanced-matching
    # but the Flask app actually calls ADO directly via ado_searcher)
    related_uats: List[RelatedUAT] = []
    search_error: str | None = None
    total_found: int = 0
    _D = "[UAT-ROUTE-DEBUG]"
    logger.info(f"{_D} ===== search_related_uats() START =====")
    logger.info(f"{_D} session_id={session_id}")
    logger.info(f"{_D} title={repr(title[:100])}")
    logger.info(f"{_D} description={repr(description[:100]) if description else '(empty)'}")
    logger.info(f"{_D} ai_services={ai_services}")
    logger.info(f"{_D} ai_keywords={ai_keywords[:10]}")
    logger.info(f"{_D} ai_concepts={ai_concepts[:10]}")
    try:
        logger.info(f"{_D} Step 1: Getting ADO searcher...")
        searcher = _get_ado_searcher()
        logger.info(f"{_D} Step 2: Calling searcher.search_uat_items() with AI context...")
        raw_results = searcher.search_uat_items(
            title=title, description=description,
            ai_services=ai_services, ai_keywords=ai_keywords,
            ai_concepts=ai_concepts,
        )
        logger.info(f"{_D} Step 3: search_uat_items returned {len(raw_results) if raw_results else 0} raw results")
        if raw_results:
            for i, r in enumerate(raw_results[:3]):
                logger.info(f"{_D}   raw[{i}] id={r.get('id')} sim={r.get('similarity')} state={r.get('state')} title={repr(r.get('title','')[:60])}")

        # Filter to last N days
        cutoff = datetime.utcnow() - timedelta(days=UAT_SEARCH_DAYS)
        logger.info(f"{_D} Step 4: Filtering to last {UAT_SEARCH_DAYS} days (cutoff={cutoff.isoformat()})")
        skipped_date = 0
        skipped_parse = 0
        for item in (raw_results or []):
            created = item.get("created_date", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if dt.replace(tzinfo=None) < cutoff:
                        skipped_date += 1
                        continue
                except (ValueError, TypeError):
                    skipped_parse += 1

            related_uats.append(RelatedUAT(
                id=item.get("id", 0),
                title=item.get("title", ""),
                url=item.get("url", ""),
                similarity=item.get("similarity", 0.0),
                state=item.get("state", ""),
                created_date=created,
                assigned_to=item.get("assigned_to", ""),
            ))

        logger.info(f"{_D} Step 5: After date filter: {len(related_uats)} kept, {skipped_date} skipped (too old), {skipped_parse} date-parse errors")

        # Sort by similarity descending
        related_uats.sort(key=lambda u: u.similarity, reverse=True)

        # Drop anything below 25 % — too noisy to display
        MIN_SIMILARITY = 0.25
        related_uats = [u for u in related_uats if u.similarity >= MIN_SIMILARITY]

        # total_found = how many passed similarity filter (before top-10 trim)
        total_found = len(related_uats)

        # Keep only the top 10 most relevant
        MAX_RELATED = 10
        related_uats = related_uats[:MAX_RELATED]

        if related_uats:
            logger.info(f"{_D} Step 6: Top 3 after sort:")
            for i, u in enumerate(related_uats[:3]):
                logger.info(f"{_D}   [{i}] id={u.id} sim={u.similarity} state={u.state} title={repr(u.title[:60])}")
        else:
            logger.info(f"{_D} Step 6: No related UATs survived filtering")

    except Exception as e:
        logger.error(f"{_D} EXCEPTION: {e}", exc_info=True)
        search_error = f"UAT search failed: {e}"

    sm.update_state(session_id, current_step=FlowStep.related_uats)
    sm.set_extra(session_id, "raw_related_uats", [u.model_dump() for u in related_uats])

    logger.info(f"{_D} ===== search_related_uats() END — returning {len(related_uats)} UATs (of {total_found} total), error={search_error} =====")

    return RelatedUATsResponse(
        session_id=session_id,
        related_uats=related_uats,
        total_found=total_found,
        search_error=search_error,
    )


# ============================================================================
# Step 8: Toggle UAT Selection
# ============================================================================

@router.post("/uats/toggle", response_model=UATSelectionResponse,
             summary="Toggle related UAT selection",
             description="Step 8: Select/deselect a related UAT (max 5).")
async def toggle_uat_selection(req: UATSelectionRequest):
    state = _get_state(req.session_id)
    sm = get_session_manager()

    selected = list(state.selected_uats)
    if req.uat_id in selected:
        selected.remove(req.uat_id)
        msg = f"UAT {req.uat_id} deselected"
    else:
        if len(selected) >= UAT_MAX_SELECTED:
            return UATSelectionResponse(
                session_id=req.session_id,
                selected_uats=selected,
                message=f"Maximum {UAT_MAX_SELECTED} UATs allowed. Deselect one first.",
            )
        selected.append(req.uat_id)
        msg = f"UAT {req.uat_id} selected"

    sm.update_state(req.session_id, selected_uats=selected)

    return UATSelectionResponse(
        session_id=req.session_id,
        selected_uats=selected,
        message=msg,
    )


# ============================================================================
# Deflection Override
# ============================================================================

@router.post("/guided-override/{session_id}",
             summary="Mark session as guided override",
             description="Records that the user was shown deflection guidance and chose to create a UAT anyway.")
async def guided_override(session_id: str):
    state = _get_state(session_id)
    sm = get_session_manager()
    sm.update_state(session_id, guided_override=True)
    return {"session_id": session_id, "guided_override": True}


# ============================================================================
# Step 9: Create UAT Work Item
# ============================================================================

@router.post("/create-uat", response_model=UATCreatedResponse,
             summary="Create UAT work item in ADO",
             description="Step 9: Creates a work item in Azure DevOps with all accumulated context.")
async def create_uat(req: UATCreateRequest):
    state = _get_state(req.session_id)
    sm = get_session_manager()

    if state.original_input is None:
        raise HTTPException(400, "No submission data in session")

    # Build wizard_data dict matching what app.py passes to create_work_item_from_issue()
    inp = state.original_input if isinstance(state.original_input, dict) else state.original_input
    title = inp.get("title", "") if isinstance(inp, dict) else inp.title
    description = inp.get("description", "") if isinstance(inp, dict) else inp.description
    impact = inp.get("impact", "") if isinstance(inp, dict) else inp.impact

    analysis = state.analysis if isinstance(state.analysis, dict) else (state.analysis.model_dump() if state.analysis else {})

    # Generate evaluation summary HTML before ADO creation so it's
    # included in the work item and also stored in Cosmos.
    summary_html = _build_evaluation_summary_html(analysis, title, state)

    wizard_data = {
        "title": title,
        "description": description,
        "impact": impact,
        "context_analysis": analysis,
        "selected_features": state.selected_features,
        "selected_uats": state.selected_uats,
        "opportunity_id": state.opportunity_id,
        "milestone_id": state.milestone_id,
        "evaluation_summary_html": summary_html,
        "guided_override": state.guided_override,
    }

    try:
        ado_client = _get_ado_client()
        result = ado_client.create_work_item_from_issue(wizard_data)
    except Exception as e:
        logger.error(f"UAT creation failed: {e}")
        raise HTTPException(502, f"Failed to create work item: {str(e)}")

    if not result or "error" in result:
        raise HTTPException(502, f"ADO returned error: {result}")

    # Get TFT feature details for response
    feature_details = sm.get_extra(req.session_id, "tft_features_detail") or []
    selected_feature_objs = [
        TFTFeature(**f) for f in feature_details if f.get("id") in state.selected_features
    ]

    work_item_id = result.get("work_item_id", result.get("id", 0))
    work_item_url = result.get("url", result.get("_links", {}).get("html", {}).get("href", ""))

    sm.update_state(req.session_id,
                    work_item_id=work_item_id,
                    work_item_url=work_item_url,
                    current_step=FlowStep.uat_created)

    # ── Store evaluation in Cosmos DB ──
    # Now that we have the work item ID, persist the AI analysis so the
    # triage system can detect it and skip re-analysis.
    corrections_dict = dict(state.corrections_applied) if state.corrections_applied else None
    eval_id = store_field_portal_evaluation(
        work_item_id=work_item_id,
        analysis=analysis,
        original_input={"title": title, "description": description, "impact": impact},
        corrections=corrections_dict,
        summary_html=summary_html,
    )
    if eval_id:
        logger.info(f"Cosmos evaluation stored: {eval_id}")
    else:
        logger.warning(f"Failed to store Cosmos evaluation for work item {work_item_id}")

    # Get UAT details for response (like features)
    raw_uats = sm.get_extra(req.session_id, "raw_related_uats") or []
    selected_uat_objs = [
        LinkedUAT(**{k: u[k] for k in ('id', 'title', 'url') if k in u})
        for u in raw_uats if u.get('id') in state.selected_uats
    ]

    return UATCreatedResponse(
        session_id=req.session_id,
        work_item_id=work_item_id,
        work_item_url=work_item_url,
        work_item_title=title,
        work_item_state="In Progress",
        assigned_to=result.get("assigned_to", "ACR Accelerate Blockers Help"),
        opportunity_id=state.opportunity_id,
        milestone_id=state.milestone_id,
        selected_features=selected_feature_objs,
        selected_uats=selected_uat_objs,
    )


# ============================================================================
# Session State
# ============================================================================

@router.get("/session/{session_id}", response_model=SessionState,
            summary="Get current session state",
            description="Returns the full state of a submission flow session.")
async def get_session_state(session_id: str):
    return _get_state(session_id)


# ============================================================================
# Diagnostics
# ============================================================================

def _mask_url(url: str) -> str:
    """Redact everything after the host so secrets/paths are not exposed."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        return f"{p.scheme}://{p.hostname}{':[port]' if p.port else ''}/"
    except Exception:
        return url[:30] + "…"


@router.get("/diagnostics",
            summary="System diagnostics",
            description="Lightweight diagnostics for the debug panel. "
                        "Returns connectivity status for every subsystem "
                        "with 5-second timeouts per check.")
async def get_diagnostics():
    import asyncio
    import time as _time
    from datetime import timezone

    CHECK_TIMEOUT = 5          # seconds per subsystem
    AI_INIT_TIMEOUT = 15       # first-time analyzer init can be slow

    diag: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api": {"status": "healthy"},
        "gateway": {},
        "cosmos": {},
        "ai": {},
        "ado_main": {},
        "ado_tft": {},
    }

    # --- Gateway ---
    async def _check_gateway():
        t0 = _time.perf_counter()
        gw = get_gateway()
        ok = await gw.check_health()
        ms = int((_time.perf_counter() - t0) * 1000)
        return {"status": "healthy" if ok else "offline", "latencyMs": ms,
                "url": _mask_url(gw.base_url)}

    try:
        diag["gateway"] = await asyncio.wait_for(
            _check_gateway(), timeout=CHECK_TIMEOUT
        )
    except asyncio.TimeoutError:
        diag["gateway"] = {"status": "timeout", "error": f"Gateway check exceeded {CHECK_TIMEOUT}s"}
    except Exception as e:
        diag["gateway"] = {"status": "error", "error": str(e)}

    # --- Cosmos DB ---
    def _check_cosmos():
        t0 = _time.perf_counter()
        from .cosmos_client import _get_cosmos
        cosmos = _get_cosmos()
        info = cosmos.health_check()
        ms = int((_time.perf_counter() - t0) * 1000)
        st = info.get("status", "healthy")
        in_mem = "in-memory" in st
        if in_mem:
            st = "healthy"
        return {"status": st, "latencyMs": ms, "inMemory": in_mem}

    try:
        diag["cosmos"] = await asyncio.wait_for(
            asyncio.to_thread(_check_cosmos), timeout=CHECK_TIMEOUT
        )
    except asyncio.TimeoutError:
        diag["cosmos"] = {"status": "timeout", "error": f"Health check exceeded {CHECK_TIMEOUT}s"}
    except Exception as e:
        diag["cosmos"] = {"status": "error", "error": str(e)}

    # --- AI / Azure OpenAI ---
    def _check_ai():
        t0 = _time.perf_counter()
        from hybrid_context_analyzer import HybridContextAnalyzer
        global _hybrid_analyzer
        if _hybrid_analyzer is None:
            _hybrid_analyzer = HybridContextAnalyzer(use_ai=True)
        analyzer = _hybrid_analyzer
        ai_info = analyzer.get_ai_status()
        ms = int((_time.perf_counter() - t0) * 1000)
        enabled = ai_info.get("enabled", False)

        cfg = getattr(analyzer, "config", None)
        aoai = getattr(cfg, "azure_openai", None) if cfg else None
        endpoint = ai_info.get("endpoint") or (getattr(aoai, "endpoint", "") if aoai else "")
        use_aad = ai_info.get("use_aad")
        if use_aad is None and aoai:
            use_aad = getattr(aoai, "use_aad", None)

        return {
            "status": "healthy" if enabled else "offline",
            "enabled": enabled,
            "latencyMs": ms,
            "reason": ai_info.get("reason"),
            "endpoint": _mask_url(endpoint),
            "useAad": use_aad,
            "initError": getattr(analyzer, "_init_error", None),
        }

    try:
        diag["ai"] = await asyncio.wait_for(
            asyncio.to_thread(_check_ai), timeout=AI_INIT_TIMEOUT
        )
    except asyncio.TimeoutError:
        diag["ai"] = {"status": "timeout", "error": f"AI check exceeded {AI_INIT_TIMEOUT}s"}
    except Exception as e:
        diag["ai"] = {"status": "error", "error": str(e)}

    # --- ADO Main Org ---
    def _check_ado_main():
        t0 = _time.perf_counter()
        from ado_integration import AzureDevOpsConfig
        cred = AzureDevOpsConfig.get_credential()
        ms = int((_time.perf_counter() - t0) * 1000)
        org = AzureDevOpsConfig.ORGANIZATION
        return {"status": "healthy", "latencyMs": ms, "org": org}

    try:
        diag["ado_main"] = await asyncio.wait_for(
            asyncio.to_thread(_check_ado_main), timeout=CHECK_TIMEOUT
        )
    except asyncio.TimeoutError:
        diag["ado_main"] = {"status": "timeout", "error": f"ADO main check exceeded {CHECK_TIMEOUT}s"}
    except Exception as e:
        diag["ado_main"] = {"status": "error", "error": str(e)}

    # --- ADO TFT Org ---
    def _check_ado_tft():
        t0 = _time.perf_counter()
        from ado_integration import AzureDevOpsConfig
        cred = AzureDevOpsConfig.get_tft_credential()
        ms = int((_time.perf_counter() - t0) * 1000)
        # Resolve TFT org name from config (same logic as get_tft_credential)
        try:
            from config import get_app_config as _gcfg
            org = _gcfg().ado_tft_organization
        except Exception:
            org = "unifiedactiontracker"
        return {"status": "healthy", "latencyMs": ms, "org": org}

    try:
        diag["ado_tft"] = await asyncio.wait_for(
            asyncio.to_thread(_check_ado_tft), timeout=CHECK_TIMEOUT
        )
    except asyncio.TimeoutError:
        diag["ado_tft"] = {"status": "timeout", "error": f"ADO TFT check exceeded {CHECK_TIMEOUT}s"}
    except Exception as e:
        diag["ado_tft"] = {"status": "error", "error": str(e)}

    return diag


# ============================================================================
# Health
# ============================================================================

@router.get("/health", response_model=HealthResponse,
            summary="Health check",
            description="Check if the field portal API and gateway are reachable.")
async def health_check():
    gw = get_gateway()
    gateway_ok = await gw.check_health()
    sm = get_session_manager()

    return HealthResponse(
        status="healthy" if gateway_ok else "degraded",
        gateway_reachable=gateway_ok,
        active_sessions=sm.active_count,
    )
