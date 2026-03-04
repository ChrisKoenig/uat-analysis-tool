"""
Admin API Routes
=================

Administrative endpoints for the new unified platform.
These replicate admin_service.py functionality (corrections, health)
without touching the legacy Flask code.

Endpoints:
    GET    /admin/corrections         — List all corrections
    POST   /admin/corrections         — Add a correction
    PUT    /admin/corrections/{id}    — Update a correction
    DELETE /admin/corrections/{id}    — Remove a correction
    POST   /admin/training-signals    — Submit a training signal
    GET    /admin/training-signals    — List training signals
    POST   /admin/tune-weights        — Run pattern weight tuning batch
    GET    /admin/pattern-weights     — View current weight adjustments
    GET    /admin/health              — Comprehensive health dashboard
    GET    /admin/health/services     — Individual service status
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("triage.api.admin")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CorrectionItem(BaseModel):
    """A single corrective learning entry."""
    id: str = Field("", description="Unique document ID")
    original_text: str = Field("", description="Text that triggered the wrong category")
    pattern: str = Field("", description="Pattern name that matched")
    original_category: str = Field(..., description="Category the system assigned")
    corrected_category: str = Field(..., description="Correct category")
    corrected_intent: str = Field("", description="Correct intent (optional)")
    correction_notes: str = Field("", description="Human explanation")
    timestamp: Optional[str] = None
    confidence_boost: float = Field(0.15, description="Extra confidence for matched corrections")
    workItemId: str = Field("general", description="Associated work item ID or 'general'")


class CorrectionCreate(BaseModel):
    """Request body for adding a correction."""
    original_text: str = Field("", description="Text that triggered the wrong category")
    pattern: str = Field("", description="Pattern name that matched")
    original_category: str = Field(..., description="Category the system assigned")
    corrected_category: str = Field(..., description="Correct category")
    corrected_intent: str = Field("", description="Correct intent")
    correction_notes: str = Field("", description="Why this is the correct category")
    confidence_boost: float = Field(0.15)


class CorrectionsListResponse(BaseModel):
    """All corrections."""
    corrections: List[CorrectionItem]
    total: int


class HealthDetail(BaseModel):
    """Detailed health for one component."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    latency_ms: Optional[int] = None
    detail: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    diagnostics: Optional[List[str]] = None


class HealthDashboardResponse(BaseModel):
    """Comprehensive health dashboard — all services at a glance."""
    overall: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    components: List[HealthDetail]
    ai_status: Optional[Dict[str, Any]] = None
    cache_stats: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Training Signal models (ENG-003 Active Learning)
# ---------------------------------------------------------------------------

class TrainingSignalCreate(BaseModel):
    """Request body for submitting a training signal."""
    workItemId: str = Field(..., description="Work item ID where disagreement was observed")
    llmCategory: str = Field(..., description="Category chosen by LLM classifier")
    llmIntent: str = Field("", description="Intent chosen by LLM classifier")
    patternCategory: str = Field(..., description="Category chosen by pattern engine")
    patternIntent: str = Field("", description="Intent chosen by pattern engine")
    humanChoice: Literal["llm", "pattern", "neither"] = Field(
        ..., description="Which classification the human selected"
    )
    resolvedCategory: str = Field("", description="Final category (auto-filled or manual for 'neither')")
    resolvedIntent: str = Field("", description="Final intent (auto-filled or manual for 'neither')")
    notes: str = Field("", description="Optional human notes on the decision")
    resolvedBy: str = Field("user", description="Who resolved the disagreement")


class TrainingSignalItem(BaseModel):
    """A stored training signal document."""
    id: str
    workItemId: str
    llmCategory: str
    llmIntent: str = ""
    patternCategory: str
    patternIntent: str = ""
    humanChoice: str  # "llm", "pattern", "neither"
    resolvedCategory: str
    resolvedIntent: str = ""
    notes: str = ""
    resolvedBy: str = "user"
    timestamp: str = ""


class TrainingSignalListResponse(BaseModel):
    """Paginated training signals list."""
    signals: List[TrainingSignalItem]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CORRECTIONS_FILE = Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))) / "corrections.json"


def _load_corrections() -> dict:
    """Load corrections.json, returning the full dict (legacy fallback)."""
    try:
        with open(_CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"version": "1.0", "corrections": []}
    except json.JSONDecodeError:
        return {"version": "1.0", "corrections": []}


def _save_corrections(data: dict):
    """Write corrections.json atomically (legacy fallback)."""
    tmp = _CORRECTIONS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(_CORRECTIONS_FILE)


_corrections_migrated = False


def _get_corrections_container():
    """Get the Cosmos corrections container, seeding from JSON if needed."""
    global _corrections_migrated
    try:
        from ..config.cosmos_config import get_cosmos_config
        cfg = get_cosmos_config()
        if cfg._in_memory:
            return None   # fall back to file
        container = cfg.get_container("corrections")
        if not _corrections_migrated:
            _seed_corrections_from_json(container)
            _corrections_migrated = True
        return container
    except Exception as e:
        logger.warning(f"Cannot get Cosmos corrections container: {e}")
        return None


def _seed_corrections_from_json(container):
    """One-time migration: seed Cosmos corrections from corrections.json."""
    try:
        existing = list(container.query_items(
            "SELECT VALUE COUNT(1) FROM c",
            enable_cross_partition_query=True
        ))
        if existing and existing[0] > 0:
            return  # already seeded
        data = _load_corrections()
        for i, corr in enumerate(data.get("corrections", [])):
            doc = {
                "id": f"corr-{uuid.uuid4().hex[:8]}",
                "workItemId": corr.get("workItemId", "general"),
                **corr,
            }
            container.upsert_item(doc)
            logger.info(f"Seeded correction {i}: {corr.get('original_category')} → {corr.get('corrected_category')}")
    except Exception as e:
        logger.warning(f"Corrections seed failed: {e}")


def _get_training_signals_container():
    """Get the Cosmos training-signals container."""
    try:
        from ..config.cosmos_config import get_cosmos_config
        cfg = get_cosmos_config()
        if cfg._in_memory:
            return None
        return cfg.get_container("training-signals")
    except Exception as e:
        logger.warning(f"Cannot get Cosmos training-signals container: {e}")
        return None


def _build_diagnostics(name: str, status: str, detail: Optional[Dict],
                       error: Optional[str]) -> List[str]:
    """
    Generate actionable diagnostic suggestions for a health component.
    Returns a list of human-readable suggestions for the operator.
    
    Note: OpenAI resource name is extracted dynamically from the endpoint URL
    (e.g., 'openai-aitriage-nonprod' from 'https://openai-aitriage-nonprod.openai.azure.com/').
    This was previously hardcoded as 'openai-bp-northcentral' (dev resource name).
    Fixed Feb 27, 2026 for environment-agnostic diagnostics.
    """
    suggestions: List[str] = []
    if status == "healthy":
        return suggestions

    if name == "azure_openai":
        if detail and not detail.get("enabled"):
            reason = detail.get("reason", "")
            if "disabled" in reason.lower():
                suggestions.append(
                    "AI services are disabled. Set the environment variable "
                    "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT to enable them."
                )
                # Extract resource name from endpoint if available
                oai_endpoint = detail.get("endpoint", "") if detail else ""
                oai_resource = oai_endpoint.split("//")[-1].split(".")[0] if oai_endpoint else "<not-configured>"
                suggestions.append(
                    f"Ensure your Azure OpenAI resource '{oai_resource}' is deployed "
                    "and you have a valid API key or AAD credential configured."
                )
                suggestions.append(
                    "If using AAD auth, set AZURE_OPENAI_USE_AAD=true and verify your "
                    "identity has the 'Cognitive Services OpenAI User' role."
                )
            if "error" in reason.lower() or "fail" in reason.lower():
                suggestions.append(
                    "AI initialization failed. Check that the deployment names in your "
                    "environment match the actual Azure OpenAI deployments."
                )
                suggestions.append(
                    "Verify network connectivity to *.openai.azure.com and ensure firewall "
                    "rules allow outbound HTTPS."
                )
        if error:
            suggestions.append(f"Raw error: {error}")
            suggestions.append(
                "Review Azure OpenAI resource quotas and ensure the model deployment "
                "has available capacity."
            )

    elif name == "cosmos_db":
        if detail and detail.get("mode") == "in-memory":
            suggestions.append(
                "Cosmos DB is running in in-memory fallback mode. Data will be lost on restart."
            )
            suggestions.append(
                "Set COSMOS_ENDPOINT and ensure your IP is in the Cosmos DB firewall "
                "allowed list (Portal → Networking → Firewall)."
            )
            suggestions.append(
                "Run 'az cosmosdb update --name <account> --resource-group <rg> "
                "--ip-range-filter <your-ip>' to add your IP."
            )
        if error:
            if "403" in str(error) or "firewall" in str(error).lower():
                suggestions.append(
                    "Access denied — your IP is likely not in the Cosmos DB firewall. "
                    "Go to Azure Portal → Cosmos DB → Networking and add your current IP."
                )
            elif "timeout" in str(error).lower():
                suggestions.append(
                    "Connection timed out. Check network/VPN connectivity and verify "
                    "the Cosmos endpoint URL is correct."
                )
            else:
                suggestions.append(f"Raw error: {error}")
                suggestions.append(
                    "Verify COSMOS_ENDPOINT and authentication credentials. "
                    "Check Azure Portal for resource status."
                )

    elif name == "key_vault":
        if error:
            if "access" in str(error).lower() or "403" in str(error):
                suggestions.append(
                    "Access denied to Key Vault. Ensure your identity has 'Key Vault Secrets "
                    "User' role (RBAC) or GET secret permission (access policies)."
                )
            suggestions.append(
                "Verify KEY_VAULT_URI is set correctly (e.g. https://kv-gcs-dev-gg4a6y.vault.azure.net/)."
            )
            suggestions.append(
                "Check that the Key Vault firewall allows your current IP or is set "
                "to 'Allow public access from all networks'."
            )

    elif name == "ado_connection":
        if error:
            suggestions.append(
                "Azure DevOps connection failed. Verify ADO_PAT is set and not expired."
            )
            suggestions.append(
                "Ensure the PAT has read access to the 'unifiedactiontracker' and "
                "'unifiedactiontrackertest' organizations."
            )
            suggestions.append(
                "Check network connectivity to https://dev.azure.com."
            )

    elif name == "local_cache":
        if error:
            suggestions.append(
                "Cache directory issue. Ensure the 'cache/ai_cache/' folder exists "
                "and is writable."
            )

    elif name == "corrections":
        if error:
            suggestions.append(
                "Cannot read corrections.json. Verify the file exists at the project root "
                "and is valid JSON."
            )

    # Generic fallback
    if not suggestions and (status != "healthy"):
        if error:
            suggestions.append(f"Error: {error}")
        suggestions.append(
            f"Component '{name}' is {status}. Check logs and Azure Portal for details."
        )

    return suggestions


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/admin", tags=["admin"])


# ==========================================================================
# Corrections endpoints
# ==========================================================================

@router.get("/corrections", response_model=CorrectionsListResponse,
            summary="List corrections")
async def list_corrections():
    """Return all corrective learning entries (Cosmos-backed with JSON fallback)."""
    container = _get_corrections_container()
    if container:
        try:
            items = list(container.query_items(
                "SELECT * FROM c ORDER BY c.timestamp DESC",
                enable_cross_partition_query=True
            ))
            corrections = [CorrectionItem(
                id=item.get("id", ""),
                original_text=item.get("original_text", ""),
                pattern=item.get("pattern", ""),
                original_category=item.get("original_category", ""),
                corrected_category=item.get("corrected_category", ""),
                corrected_intent=item.get("corrected_intent", ""),
                correction_notes=item.get("correction_notes", ""),
                timestamp=item.get("timestamp"),
                confidence_boost=item.get("confidence_boost", 0.15),
                workItemId=item.get("workItemId", "general"),
            ) for item in items]
            return CorrectionsListResponse(corrections=corrections, total=len(corrections))
        except Exception as e:
            logger.warning(f"Cosmos corrections read failed, falling back to JSON: {e}")
    # Fallback to JSON
    data = _load_corrections()
    items = data.get("corrections", [])
    return CorrectionsListResponse(
        corrections=[CorrectionItem(
            id=f"legacy-{i}",
            original_category=c.get("original_category", ""),
            corrected_category=c.get("corrected_category", ""),
            **{k: c[k] for k in c if k not in ("original_category", "corrected_category")}
        ) for i, c in enumerate(items)],
        total=len(items),
    )


@router.post("/corrections", response_model=CorrectionItem, status_code=201,
             summary="Add a correction")
async def add_correction(req: CorrectionCreate):
    """
    Add a new corrective learning entry.

    The hybrid analyzer will use this to bias future classifications
    for similar text toward the corrected category/intent.
    """
    doc_id = f"corr-{uuid.uuid4().hex[:8]}"
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": doc_id,
        "workItemId": "general",
        "original_text": req.original_text,
        "pattern": req.pattern,
        "original_category": req.original_category,
        "corrected_category": req.corrected_category,
        "corrected_intent": req.corrected_intent,
        "correction_notes": req.correction_notes,
        "timestamp": ts,
        "confidence_boost": req.confidence_boost,
    }
    container = _get_corrections_container()
    if container:
        try:
            container.upsert_item(entry)
            logger.info(f"Added correction {doc_id}: {req.original_category} → {req.corrected_category}")
            return CorrectionItem(**entry)
        except Exception as e:
            logger.warning(f"Cosmos correction write failed, falling back to JSON: {e}")
    # Fallback to JSON
    data = _load_corrections()
    data.setdefault("corrections", []).append(entry)
    _save_corrections(data)
    logger.info(f"Added correction (JSON): {req.original_category} → {req.corrected_category}")
    return CorrectionItem(**entry)


@router.delete("/corrections/{correction_id}", status_code=204,
               summary="Delete a correction")
async def delete_correction(correction_id: str):
    """Remove a correction by its document ID."""
    container = _get_corrections_container()
    if container:
        try:
            # Try to read the item first to get its partition key
            items = list(container.query_items(
                f"SELECT * FROM c WHERE c.id = @id",
                parameters=[{"name": "@id", "value": correction_id}],
                enable_cross_partition_query=True
            ))
            if not items:
                raise HTTPException(404, f"Correction {correction_id} not found")
            pk = items[0].get("workItemId", "general")
            container.delete_item(item=correction_id, partition_key=pk)
            logger.info(f"Deleted correction {correction_id}")
            return None
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Cosmos delete failed, falling back: {e}")
    # Fallback: index-based for legacy IDs like "legacy-0"
    if correction_id.startswith("legacy-"):
        idx = int(correction_id.split("-")[1])
        data = _load_corrections()
        corrections = data.get("corrections", [])
        if idx < 0 or idx >= len(corrections):
            raise HTTPException(404, f"Correction {correction_id} not found")
        corrections.pop(idx)
        _save_corrections(data)
        logger.info(f"Deleted legacy correction #{idx}")
        return None
    raise HTTPException(404, f"Correction {correction_id} not found")


@router.put("/corrections/{correction_id}", response_model=CorrectionItem,
            summary="Update a correction")
async def update_correction(correction_id: str, req: CorrectionCreate):
    """Update an existing correction by its document ID."""
    container = _get_corrections_container()
    if container:
        try:
            items = list(container.query_items(
                f"SELECT * FROM c WHERE c.id = @id",
                parameters=[{"name": "@id", "value": correction_id}],
                enable_cross_partition_query=True
            ))
            if not items:
                raise HTTPException(404, f"Correction {correction_id} not found")
            existing = items[0]
            updated = {
                "id": correction_id,
                "workItemId": existing.get("workItemId", "general"),
                "original_text": req.original_text,
                "pattern": req.pattern,
                "original_category": req.original_category,
                "corrected_category": req.corrected_category,
                "corrected_intent": req.corrected_intent,
                "correction_notes": req.correction_notes,
                "timestamp": existing.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "confidence_boost": req.confidence_boost,
            }
            container.upsert_item(updated)
            logger.info(f"Updated correction {correction_id}: {req.original_category} → {req.corrected_category}")
            return CorrectionItem(**updated)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Cosmos update failed, falling back: {e}")
    # Fallback for legacy IDs
    if correction_id.startswith("legacy-"):
        idx = int(correction_id.split("-")[1])
        data = _load_corrections()
        corrections = data.get("corrections", [])
        if idx < 0 or idx >= len(corrections):
            raise HTTPException(404, f"Correction {correction_id} not found")
        updated = {
            "id": correction_id,
            "workItemId": "general",
            "original_text": req.original_text,
            "pattern": req.pattern,
            "original_category": req.original_category,
            "corrected_category": req.corrected_category,
            "corrected_intent": req.corrected_intent,
            "correction_notes": req.correction_notes,
            "timestamp": corrections[idx].get("timestamp", datetime.now(timezone.utc).isoformat()),
            "confidence_boost": req.confidence_boost,
        }
        corrections[idx] = updated
        _save_corrections(data)
        logger.info(f"Updated legacy correction #{idx}")
        return CorrectionItem(**updated)
    raise HTTPException(404, f"Correction {correction_id} not found")


# ==========================================================================
# Training Signal endpoints (ENG-003 Active Learning)
# ==========================================================================

@router.post("/training-signals", response_model=TrainingSignalItem, status_code=201,
             summary="Submit a training signal")
async def submit_training_signal(req: TrainingSignalCreate):
    """
    Record a human resolution of an LLM/Pattern disagreement.

    The 'humanChoice' field indicates which classifier the human agreed with:
      - "llm"     → LLM was correct
      - "pattern" → Pattern engine was correct
      - "neither" → Both wrong; resolvedCategory/resolvedIntent specified manually
    """
    doc_id = f"ts-{uuid.uuid4().hex[:8]}"
    ts = datetime.now(timezone.utc).isoformat()

    # Auto-fill resolved category/intent from the chosen classifier
    resolved_cat = req.resolvedCategory
    resolved_int = req.resolvedIntent
    if req.humanChoice == "llm" and not resolved_cat:
        resolved_cat = req.llmCategory
        resolved_int = req.llmIntent
    elif req.humanChoice == "pattern" and not resolved_cat:
        resolved_cat = req.patternCategory
        resolved_int = req.patternIntent

    doc = {
        "id": doc_id,
        "workItemId": req.workItemId,
        "llmCategory": req.llmCategory,
        "llmIntent": req.llmIntent,
        "patternCategory": req.patternCategory,
        "patternIntent": req.patternIntent,
        "humanChoice": req.humanChoice,
        "resolvedCategory": resolved_cat,
        "resolvedIntent": resolved_int,
        "notes": req.notes,
        "resolvedBy": req.resolvedBy,
        "timestamp": ts,
    }

    container = _get_training_signals_container()
    if container:
        try:
            container.upsert_item(doc)
            logger.info(
                f"Training signal {doc_id}: work item {req.workItemId}, "
                f"choice={req.humanChoice}, resolved={resolved_cat}"
            )
            return TrainingSignalItem(**doc)
        except Exception as e:
            logger.error(f"Failed to store training signal: {e}")
            raise HTTPException(500, f"Failed to store training signal: {e}")
    else:
        raise HTTPException(503, "Training signals require Cosmos DB (not available in fallback mode)")


@router.get("/training-signals", response_model=TrainingSignalListResponse,
            summary="List training signals")
async def list_training_signals(
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    work_item_id: Optional[str] = Query(None, description="Filter by work item ID"),
):
    """Return recent training signals, optionally filtered by work item."""
    container = _get_training_signals_container()
    if not container:
        raise HTTPException(503, "Training signals require Cosmos DB")

    try:
        if work_item_id:
            query = "SELECT * FROM c WHERE c.workItemId = @wid ORDER BY c.timestamp DESC"
            params = [{"name": "@wid", "value": work_item_id}]
        else:
            query = "SELECT * FROM c ORDER BY c.timestamp DESC"
            params = []
        items = list(container.query_items(
            query, parameters=params, enable_cross_partition_query=True,
            max_item_count=limit,
        ))[:limit]
        signals = [TrainingSignalItem(
            id=item.get("id", ""),
            workItemId=item.get("workItemId", ""),
            llmCategory=item.get("llmCategory", ""),
            llmIntent=item.get("llmIntent", ""),
            patternCategory=item.get("patternCategory", ""),
            patternIntent=item.get("patternIntent", ""),
            humanChoice=item.get("humanChoice", ""),
            resolvedCategory=item.get("resolvedCategory", ""),
            resolvedIntent=item.get("resolvedIntent", ""),
            notes=item.get("notes", ""),
            resolvedBy=item.get("resolvedBy", "user"),
            timestamp=item.get("timestamp", ""),
        ) for item in items]
        return TrainingSignalListResponse(signals=signals, total=len(signals))
    except Exception as e:
        logger.error(f"Failed to list training signals: {e}")
        raise HTTPException(500, f"Failed to read training signals: {e}")


# ==========================================================================
# Pattern weight tuning endpoints (ENG-003 Step 3)
# ==========================================================================

class WeightAdjustmentDetail(BaseModel):
    multiplier: float = 1.0
    accuracy: float = 0.0
    signals: int = 0
    pattern_wins: int = 0
    llm_wins: int = 0
    neither_wins: int = 0
    status: str = "neutral"

class WeightTuningResponse(BaseModel):
    status: str = "ok"
    message: str = ""
    totalSignals: int = 0
    adjustments: Dict[str, WeightAdjustmentDetail] = {}
    lastTuned: str = ""


@router.post("/tune-weights", response_model=WeightTuningResponse,
             summary="Run pattern weight tuning batch",
             description="Reads training signals, computes per-category weight adjustments, and stores them for the pattern engine.")
async def tune_pattern_weights():
    """Execute the weight tuning batch process."""
    try:
        from weight_tuner import PatternWeightTuner
        tuner = PatternWeightTuner()
        doc = tuner.run()

        if doc.get("status") == "no_signals":
            return WeightTuningResponse(
                status="no_signals",
                message=doc.get("message", "No training signals found."),
                totalSignals=0,
            )

        return WeightTuningResponse(
            status="ok",
            message=f"Tuned weights from {doc.get('totalSignals', 0)} signals.",
            totalSignals=doc.get("totalSignals", 0),
            adjustments={
                k: WeightAdjustmentDetail(**v)
                for k, v in doc.get("adjustments", {}).items()
            },
            lastTuned=doc.get("lastTuned", ""),
        )
    except Exception as e:
        logger.error(f"Weight tuning failed: {e}")
        raise HTTPException(500, f"Weight tuning failed: {e}")


@router.get("/pattern-weights", response_model=WeightTuningResponse,
            summary="Get current pattern weight adjustments",
            description="Returns the most recent weight adjustments computed by the tuning batch.")
async def get_pattern_weights():
    """Return the stored weight adjustments document."""
    try:
        from weight_tuner import PatternWeightTuner
        tuner = PatternWeightTuner()
        doc = tuner.get_weights()

        if doc is None:
            return WeightTuningResponse(
                status="not_tuned",
                message="No weight adjustments found. Run POST /admin/tune-weights first.",
                totalSignals=0,
            )

        return WeightTuningResponse(
            status="ok",
            message="Current weight adjustments.",
            totalSignals=doc.get("totalSignals", 0),
            adjustments={
                k: WeightAdjustmentDetail(**v)
                for k, v in doc.get("adjustments", {}).items()
            },
            lastTuned=doc.get("lastTuned", ""),
        )
    except Exception as e:
        logger.error(f"Failed to read pattern weights: {e}")
        raise HTTPException(500, f"Failed to read pattern weights: {e}")


# ==========================================================================
# Health dashboard endpoints
# ==========================================================================

@router.get("/health", response_model=HealthDashboardResponse,
            summary="Comprehensive health dashboard")
async def health_dashboard():
    """
    Check every component: Cosmos DB, Azure OpenAI, Key Vault, ADO, cache.
    Returns an aggregate status and per-component detail.
    """
    components: List[HealthDetail] = []
    overall = "healthy"

    # --- Cosmos DB ---
    try:
        t0 = time.perf_counter()
        from ..config.cosmos_config import get_cosmos_config
        cfg = get_cosmos_config()
        if cfg._in_memory:
            latency = int((time.perf_counter() - t0) * 1000)
            components.append(HealthDetail(
                name="cosmos_db",
                status="degraded",
                latency_ms=latency,
                detail={"mode": "in-memory", "database": cfg.database_name},
            ))
            if overall == "healthy":
                overall = "degraded"
        else:
            cfg._ensure_database()
            db = cfg._database
            containers = list(db.list_containers())
            latency = int((time.perf_counter() - t0) * 1000)
            components.append(HealthDetail(
                name="cosmos_db",
                status="healthy",
                latency_ms=latency,
                detail={"database": db.id, "containers": len(containers)},
            ))
    except Exception as e:
        overall = "degraded"
        components.append(HealthDetail(
            name="cosmos_db", status="unhealthy", error=str(e),
        ))

    # --- Azure OpenAI ---
    ai_status = None
    try:
        t0 = time.perf_counter()
        import sys
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from hybrid_context_analyzer import HybridContextAnalyzer
        analyzer = HybridContextAnalyzer(use_ai=True)
        ai_status = analyzer.get_ai_status()
        latency = int((time.perf_counter() - t0) * 1000)
        if ai_status.get("enabled"):
            components.append(HealthDetail(
                name="azure_openai", status="healthy", latency_ms=latency,
                detail=ai_status,
            ))
        else:
            overall = "degraded" if overall == "healthy" else overall
            components.append(HealthDetail(
                name="azure_openai", status="degraded", latency_ms=latency,
                detail=ai_status,
            ))
    except Exception as e:
        overall = "degraded" if overall == "healthy" else overall
        components.append(HealthDetail(
            name="azure_openai", status="unhealthy", error=str(e),
        ))

    # --- Key Vault ---
    try:
        t0 = time.perf_counter()
        from keyvault_config import KeyVaultConfig, KEY_VAULT_URI
        kv = KeyVaultConfig()
        # extract short vault name from URI (e.g. "kv-gcs-dev-gg4a6y")
        from urllib.parse import urlparse
        vault_name = urlparse(KEY_VAULT_URI).hostname.split(".")[0] if KEY_VAULT_URI else "unknown"
        latency = int((time.perf_counter() - t0) * 1000)
        components.append(HealthDetail(
            name="key_vault", status="healthy", latency_ms=latency,
            detail={"vault": vault_name},
        ))
    except Exception as e:
        components.append(HealthDetail(
            name="key_vault", status="degraded", error=str(e),
        ))

    # --- ADO connection ---
    try:
        t0 = time.perf_counter()
        from ..services.ado_client import get_ado_client
        ado = get_ado_client()
        # check if ADO config is available
        latency = int((time.perf_counter() - t0) * 1000)
        components.append(HealthDetail(
            name="ado_connection", status="healthy", latency_ms=latency,
            detail={"read_org": "unifiedactiontracker", "write_org": "unifiedactiontrackertest"},
        ))
    except Exception as e:
        components.append(HealthDetail(
            name="ado_connection", status="degraded", error=str(e),
        ))

    # --- Local cache ---
    cache_stats = None
    try:
        cache_dir = Path(project_root) / "cache" / "ai_cache"
        if cache_dir.exists():
            files = list(cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in files)
            cache_stats = {
                "files": len(files),
                "total_size_kb": round(total_size / 1024, 1),
            }
            components.append(HealthDetail(
                name="local_cache", status="healthy",
                detail=cache_stats,
            ))
        else:
            components.append(HealthDetail(
                name="local_cache", status="healthy",
                detail={"files": 0, "total_size_kb": 0},
            ))
    except Exception as e:
        components.append(HealthDetail(
            name="local_cache", status="degraded", error=str(e),
        ))

    # --- Corrections file ---
    try:
        data = _load_corrections()
        count = len(data.get("corrections", []))
        components.append(HealthDetail(
            name="corrections", status="healthy",
            detail={"entries": count, "file": str(_CORRECTIONS_FILE)},
        ))
    except Exception as e:
        components.append(HealthDetail(
            name="corrections", status="degraded", error=str(e),
        ))

    # --- Attach diagnostics to each component ---
    for comp in components:
        comp.diagnostics = _build_diagnostics(
            comp.name, comp.status, comp.detail, comp.error
        )

    return HealthDashboardResponse(
        overall=overall,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components,
        ai_status=ai_status,
        cache_stats=cache_stats,
    )
