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
    GET    /admin/agreement-rate       — Agreement rate metric
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

    elif name == "servicetree_catalog":
        if detail and detail.get("services", 0) == 0:
            suggestions.append(
                "ServiceTree catalog is empty. Try POST /admin/servicetree/refresh?force=true "
                "to reload from the ServiceTree API."
            )
            suggestions.append(
                "Ensure you are logged in to the corp tenant: "
                "az login --tenant 72f988bf-86f1-41af-91ab-2d7cd011db47"
            )
        if error:
            suggestions.append(f"ServiceTree error: {error}")
            suggestions.append(
                "Verify the ServiceTree BFF at tf-servicetree-api.azurewebsites.net is accessible "
                "and your token for api://73b8d7d8-5640-4047-879f-7f0a0298905b is valid."
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
# Agreement Rate Metric  (ENG-003 Step 5)
# ==========================================================================

class PeriodStats(BaseModel):
    """Agreement statistics for a time period."""
    total: int = 0
    agreements: int = 0
    disagreements: int = 0
    rate: float = 0.0

class AgreementRateResponse(BaseModel):
    """Overall and per-period agreement rate between pattern engine and LLM."""
    total: int = 0
    agreements: int = 0
    disagreements: int = 0
    rate: float = 0.0
    trainingSignals: int = 0
    periods: Dict[str, PeriodStats] = {}


@router.get("/agreement-rate", response_model=AgreementRateResponse,
            summary="Agreement rate between pattern engine and LLM")
async def get_agreement_rate():
    """
    Compute the agreement rate between the pattern engine and LLM classifier
    across all stored analysis results, with breakdowns for the last 7, 30,
    and 90 days.
    """
    from ..config.cosmos_config import get_cosmos_config
    cosmos = get_cosmos_config()

    # -- Query analysis results for agreement field --
    try:
        container = cosmos.get_container("analysis-results")
        query = "SELECT c.agreement, c.timestamp FROM c WHERE IS_DEFINED(c.agreement)"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
    except Exception as e:
        logger.warning(f"Agreement rate query failed: {e}")
        items = []

    # -- Count training signals (excluding system doc) --
    training_signal_count = 0
    try:
        ts_container = cosmos.get_container("training-signals")
        count_query = "SELECT VALUE COUNT(1) FROM c WHERE c.workItemId != '_system'"
        result = list(ts_container.query_items(query=count_query, enable_cross_partition_query=True))
        training_signal_count = result[0] if result else 0
    except Exception as e:
        logger.warning(f"Training signal count failed: {e}")

    # -- Compute overall stats --
    now = datetime.now(timezone.utc)
    period_boundaries = {
        "last7days": now - __import__("datetime").timedelta(days=7),
        "last30days": now - __import__("datetime").timedelta(days=30),
        "last90days": now - __import__("datetime").timedelta(days=90),
    }
    period_stats: Dict[str, Dict[str, int]] = {
        k: {"total": 0, "agreements": 0, "disagreements": 0}
        for k in period_boundaries
    }

    total = 0
    agreements = 0

    for item in items:
        agreed = item.get("agreement", False)
        total += 1
        if agreed:
            agreements += 1

        # Parse timestamp for period bucketing
        ts_raw = item.get("timestamp", "")
        try:
            if isinstance(ts_raw, str) and ts_raw:
                ts_dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            else:
                continue
        except (ValueError, TypeError):
            continue

        for period_name, boundary in period_boundaries.items():
            if ts_dt >= boundary:
                period_stats[period_name]["total"] += 1
                if agreed:
                    period_stats[period_name]["agreements"] += 1
                else:
                    period_stats[period_name]["disagreements"] += 1

    disagreements = total - agreements
    rate = (agreements / total) if total > 0 else 0.0

    periods_out = {}
    for k, v in period_stats.items():
        p_rate = (v["agreements"] / v["total"]) if v["total"] > 0 else 0.0
        v["disagreements"] = v["total"] - v["agreements"]
        periods_out[k] = PeriodStats(
            total=v["total"],
            agreements=v["agreements"],
            disagreements=v["disagreements"],
            rate=round(p_rate, 4),
        )

    return AgreementRateResponse(
        total=total,
        agreements=agreements,
        disagreements=disagreements,
        rate=round(rate, 4),
        trainingSignals=training_signal_count,
        periods=periods_out,
    )


# ==========================================================================
# ServiceTree catalog management endpoints
# ==========================================================================

class ServiceTreeOverrideRequest(BaseModel):
    """Request body for overriding ServiceTree routing fields."""
    csuDri: Optional[str] = Field(None, description="Override CSU DRI alias")
    areaPathAdo: Optional[str] = Field(None, description="Override ADO area path")
    solutionAreaGcs: Optional[str] = Field(None, description="Override solution area")
    releaseManager: Optional[str] = Field(None, description="Override release manager")
    devContact: Optional[str] = Field(None, description="Override dev contact")
    notes: Optional[str] = Field(None, description="Admin notes on why override was applied")


class ServiceTreeOverrideItem(BaseModel):
    """A stored ServiceTree override."""
    serviceName: str
    overrides: Dict[str, Any]
    appliedBy: str = "admin"
    appliedAt: str = ""


class ServiceTreeCatalogResponse(BaseModel):
    """Summary of the ServiceTree catalog."""
    totalServices: int
    totalOfferings: int
    solutionAreas: List[str]
    areaPaths: List[str]
    cacheAge: Optional[str] = None
    lastRefresh: Optional[str] = None
    overrideCount: int = 0


class ServiceTreeSearchResponse(BaseModel):
    """Search results from ServiceTree catalog."""
    query: str
    results: List[Dict[str, Any]]
    total: int


def _get_servicetree_service():
    """Get the ServiceTree service singleton (lazy import from project root)."""
    import sys
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from servicetree_service import get_servicetree_service
    return get_servicetree_service()


def _get_servicetree_container():
    """Get the Cosmos DB servicetree-catalog container."""
    try:
        from ..config.cosmos_config import get_cosmos_config
        cfg = get_cosmos_config()
        if cfg._in_memory:
            return None
        return cfg.get_container("servicetree-catalog")
    except Exception as e:
        logger.warning(f"Cannot get servicetree-catalog container: {e}")
        return None


@router.get("/servicetree/catalog", response_model=ServiceTreeCatalogResponse,
            summary="ServiceTree catalog summary")
async def servicetree_catalog_summary():
    """Return summary stats about the cached ServiceTree catalog."""
    try:
        svc = _get_servicetree_service()
        stats = svc.get_catalog_stats()

        # Count overrides from Cosmos
        override_count = 0
        container = _get_servicetree_container()
        if container:
            try:
                result = list(container.query_items(
                    "SELECT VALUE COUNT(1) FROM c WHERE c.docType = 'override'",
                    enable_cross_partition_query=True,
                ))
                override_count = result[0] if result else 0
            except Exception:
                pass

        return ServiceTreeCatalogResponse(
            totalServices=stats.get("total_services", 0),
            totalOfferings=stats.get("total_offerings", 0),
            solutionAreas=stats.get("solution_areas", []),
            areaPaths=stats.get("area_paths", []),
            cacheAge=stats.get("cache_age", None),
            lastRefresh=stats.get("last_refresh", None),
            overrideCount=override_count,
        )
    except Exception as e:
        logger.error(f"ServiceTree catalog summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servicetree/search", response_model=ServiceTreeSearchResponse,
            summary="Search ServiceTree catalog")
async def servicetree_search(
    q: str = Query(..., min_length=1, description="Service or product name to search"),
    limit: int = Query(20, ge=1, le=100),
):
    """Search the ServiceTree catalog by service name (fuzzy match)."""
    try:
        svc = _get_servicetree_service()
        catalog = svc.get_catalog()

        q_lower = q.strip().lower()
        matches = []
        for entry in catalog:
            name = entry.get("name", "").lower()
            offering = entry.get("offeringName", "").lower()
            if q_lower in name or q_lower in offering or name in q_lower:
                matches.append(entry)

        # If no substring matches, try fuzzy
        if not matches:
            from difflib import SequenceMatcher
            scored = []
            for entry in catalog:
                ratio = SequenceMatcher(None, q_lower, entry.get("name", "").lower()).ratio()
                if ratio >= 0.5:
                    scored.append((ratio, entry))
            scored.sort(key=lambda x: x[0], reverse=True)
            matches = [e for _, e in scored[:limit]]

        return ServiceTreeSearchResponse(
            query=q,
            results=matches[:limit],
            total=len(matches),
        )
    except Exception as e:
        logger.error(f"ServiceTree search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servicetree/services", summary="List all ServiceTree services")
async def servicetree_list_services(
    solutionArea: Optional[str] = Query(None, description="Filter by solution area"),
    offering: Optional[str] = Query(None, description="Filter by offering name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    """List ServiceTree services with optional filters and pagination."""
    try:
        svc = _get_servicetree_service()
        catalog = svc.get_catalog()

        filtered = catalog
        if solutionArea:
            filtered = [e for e in filtered
                        if e.get("solutionAreaGcs", "").lower() == solutionArea.lower()]
        if offering:
            filtered = [e for e in filtered
                        if e.get("offeringName", "").lower() == offering.lower()]

        total = len(filtered)
        page = filtered[skip:skip + limit]

        return {
            "services": page,
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/servicetree/refresh", summary="Refresh ServiceTree catalog")
async def servicetree_refresh(force: bool = Query(False)):
    """Trigger a manual refresh of the ServiceTree catalog from the API."""
    try:
        svc = _get_servicetree_service()
        svc.refresh(force=force)
        stats = svc.get_catalog_stats()
        logger.info("ServiceTree catalog refreshed (force=%s): %d services", force, stats.get("total_services", 0))
        return {
            "status": "refreshed",
            "force": force,
            "totalServices": stats.get("total_services", 0),
            "totalOfferings": stats.get("total_offerings", 0),
        }
    except Exception as e:
        logger.error(f"ServiceTree refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/servicetree/override/{service_name}",
            summary="Apply admin override for a ServiceTree service")
async def servicetree_apply_override(service_name: str, body: ServiceTreeOverrideRequest):
    """
    Override routing fields (csuDri, areaPathAdo, etc.) for a specific service.
    Overrides persist across catalog refreshes.
    """
    try:
        # Build override dict (only non-None fields)
        overrides = {k: v for k, v in body.dict().items() if v is not None and k != "notes"}

        if not overrides:
            raise HTTPException(status_code=400, detail="No override fields provided")

        # Store override in Cosmos
        container = _get_servicetree_container()
        now_iso = datetime.now(timezone.utc).isoformat()
        doc = {
            "id": f"override-{service_name.lower().replace(' ', '-')}",
            "docType": "override",
            "serviceName": service_name,
            "overrides": overrides,
            "notes": body.notes or "",
            "appliedBy": "admin",
            "appliedAt": now_iso,
            "solutionArea": "override",  # partition key
        }

        if container:
            container.upsert_item(doc)
            logger.info("ServiceTree override saved to Cosmos: %s → %s", service_name, overrides)
        else:
            # File-based fallback
            override_file = Path(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            )))) / ".cache" / "servicetree_overrides.json"
            override_file.parent.mkdir(parents=True, exist_ok=True)
            existing = {}
            if override_file.exists():
                with open(override_file, "r") as f:
                    existing = json.load(f)
            existing[service_name] = {
                "overrides": overrides,
                "notes": body.notes or "",
                "appliedBy": "admin",
                "appliedAt": now_iso,
            }
            with open(override_file, "w") as f:
                json.dump(existing, f, indent=2)
            logger.info("ServiceTree override saved to file: %s → %s", service_name, overrides)

        # Apply override to in-memory catalog
        svc = _get_servicetree_service()
        svc.apply_overrides({service_name: overrides})

        return {
            "status": "override_applied",
            "serviceName": service_name,
            "overrides": overrides,
            "appliedAt": now_iso,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ServiceTree override failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/servicetree/overrides", summary="List all ServiceTree overrides")
async def servicetree_list_overrides():
    """List all admin overrides currently applied to ServiceTree services."""
    try:
        container = _get_servicetree_container()
        overrides = []

        if container:
            try:
                items = list(container.query_items(
                    "SELECT * FROM c WHERE c.docType = 'override' ORDER BY c.appliedAt DESC",
                    enable_cross_partition_query=True,
                ))
                overrides = [ServiceTreeOverrideItem(
                    serviceName=item.get("serviceName", ""),
                    overrides=item.get("overrides", {}),
                    appliedBy=item.get("appliedBy", "admin"),
                    appliedAt=item.get("appliedAt", ""),
                ) for item in items]
            except Exception as e:
                logger.warning(f"Cosmos override query failed: {e}")

        if not overrides:
            # File-based fallback
            override_file = Path(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            )))) / ".cache" / "servicetree_overrides.json"
            if override_file.exists():
                with open(override_file, "r") as f:
                    data = json.load(f)
                overrides = [ServiceTreeOverrideItem(
                    serviceName=svc_name,
                    overrides=info.get("overrides", {}),
                    appliedBy=info.get("appliedBy", "admin"),
                    appliedAt=info.get("appliedAt", ""),
                ) for svc_name, info in data.items()]

        return {"overrides": overrides, "total": len(overrides)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/servicetree/override/{service_name}",
               summary="Remove admin override for a ServiceTree service")
async def servicetree_remove_override(service_name: str):
    """Remove an admin override, reverting to original ServiceTree data."""
    try:
        container = _get_servicetree_container()
        doc_id = f"override-{service_name.lower().replace(' ', '-')}"

        deleted = False
        if container:
            try:
                container.delete_item(doc_id, partition_key="override")
                deleted = True
                logger.info("ServiceTree override removed from Cosmos: %s", service_name)
            except Exception as e:
                if "NotFound" not in str(e):
                    logger.warning(f"Cosmos override delete failed: {e}")

        if not deleted:
            # File-based fallback
            override_file = Path(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)
            )))) / ".cache" / "servicetree_overrides.json"
            if override_file.exists():
                with open(override_file, "r") as f:
                    data = json.load(f)
                if service_name in data:
                    del data[service_name]
                    with open(override_file, "w") as f:
                        json.dump(data, f, indent=2)
                    deleted = True

        if not deleted:
            raise HTTPException(status_code=404, detail=f"No override found for '{service_name}'")

        return {"status": "override_removed", "serviceName": service_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

    # --- ServiceTree catalog ---
    try:
        t0 = time.perf_counter()
        st_svc = _get_servicetree_service()
        st_stats = st_svc.get_catalog_stats()
        latency = int((time.perf_counter() - t0) * 1000)
        total_svc = st_stats.get("total_services", 0)
        if total_svc > 0:
            components.append(HealthDetail(
                name="servicetree_catalog", status="healthy", latency_ms=latency,
                detail={
                    "services": total_svc,
                    "offerings": st_stats.get("total_offerings", 0),
                    "cache_age": st_stats.get("cache_age"),
                },
            ))
        else:
            overall = "degraded" if overall == "healthy" else overall
            components.append(HealthDetail(
                name="servicetree_catalog", status="degraded", latency_ms=latency,
                detail={"services": 0, "reason": "catalog empty or not loaded"},
            ))
    except Exception as e:
        components.append(HealthDetail(
            name="servicetree_catalog", status="degraded", error=str(e),
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
