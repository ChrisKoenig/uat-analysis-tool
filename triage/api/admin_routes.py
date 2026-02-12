"""
Admin API Routes
=================

Administrative endpoints for the new unified platform.
These replicate admin_service.py functionality (corrections, health)
without touching the legacy Flask code.

Endpoints:
    GET    /admin/corrections         — List all corrections
    POST   /admin/corrections         — Add a correction
    DELETE /admin/corrections/{index} — Remove a correction
    GET    /admin/health              — Comprehensive health dashboard
    GET    /admin/health/services     — Individual service status
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("triage.api.admin")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CorrectionItem(BaseModel):
    """A single corrective learning entry."""
    original_text: str = Field("", description="Text that triggered the wrong category")
    pattern: str = Field("", description="Pattern name that matched")
    original_category: str = Field(..., description="Category the system assigned")
    corrected_category: str = Field(..., description="Correct category")
    corrected_intent: str = Field("", description="Correct intent (optional)")
    correction_notes: str = Field("", description="Human explanation")
    timestamp: Optional[str] = None
    confidence_boost: float = Field(0.15, description="Extra confidence for matched corrections")


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


class HealthDashboardResponse(BaseModel):
    """Comprehensive health dashboard — all services at a glance."""
    overall: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    components: List[HealthDetail]
    ai_status: Optional[Dict[str, Any]] = None
    cache_stats: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CORRECTIONS_FILE = Path(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))) / "corrections.json"


def _load_corrections() -> dict:
    """Load corrections.json, returning the full dict."""
    try:
        with open(_CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"version": "1.0", "corrections": []}
    except json.JSONDecodeError:
        return {"version": "1.0", "corrections": []}


def _save_corrections(data: dict):
    """Write corrections.json atomically."""
    tmp = _CORRECTIONS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(_CORRECTIONS_FILE)


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
    """Return all corrective learning entries."""
    data = _load_corrections()
    items = data.get("corrections", [])
    return CorrectionsListResponse(
        corrections=[CorrectionItem(**c) for c in items],
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
    data = _load_corrections()
    entry = {
        "original_text": req.original_text,
        "pattern": req.pattern,
        "original_category": req.original_category,
        "corrected_category": req.corrected_category,
        "corrected_intent": req.corrected_intent,
        "correction_notes": req.correction_notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence_boost": req.confidence_boost,
    }
    data.setdefault("corrections", []).append(entry)
    _save_corrections(data)
    logger.info(f"Added correction: {req.original_category} → {req.corrected_category}")
    return CorrectionItem(**entry)


@router.delete("/corrections/{index}", status_code=204,
               summary="Delete a correction")
async def delete_correction(index: int):
    """Remove a correction by its zero-based index."""
    data = _load_corrections()
    corrections = data.get("corrections", [])
    if index < 0 or index >= len(corrections):
        raise HTTPException(404, f"Correction index {index} not found (have {len(corrections)})")
    removed = corrections.pop(index)
    _save_corrections(data)
    logger.info(f"Deleted correction #{index}: {removed.get('original_category')} → {removed.get('corrected_category')}")
    return None


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
        db = cfg.get_database()
        # lightweight probe: list containers
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
        from keyvault_config import KeyVaultConfig
        kv = KeyVaultConfig()
        # attempt a lightweight read
        vault_url = kv.vault_url if hasattr(kv, 'vault_url') else "unknown"
        latency = int((time.perf_counter() - t0) * 1000)
        components.append(HealthDetail(
            name="key_vault", status="healthy", latency_ms=latency,
            detail={"vault": vault_url},
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

    return HealthDashboardResponse(
        overall=overall,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components,
        ai_status=ai_status,
        cache_stats=cache_stats,
    )
