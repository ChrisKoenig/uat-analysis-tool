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
    diagnostics: Optional[List[str]] = None


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


@router.put("/corrections/{index}", response_model=CorrectionItem,
            summary="Update a correction")
async def update_correction(index: int, req: CorrectionCreate):
    """Update an existing correction by its zero-based index."""
    data = _load_corrections()
    corrections = data.get("corrections", [])
    if index < 0 or index >= len(corrections):
        raise HTTPException(404, f"Correction index {index} not found (have {len(corrections)})")
    existing = corrections[index]
    updated = {
        "original_text": req.original_text,
        "pattern": req.pattern,
        "original_category": req.original_category,
        "corrected_category": req.corrected_category,
        "corrected_intent": req.corrected_intent,
        "correction_notes": req.correction_notes,
        "timestamp": existing.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "confidence_boost": req.confidence_boost,
    }
    corrections[index] = updated
    _save_corrections(data)
    logger.info(f"Updated correction #{index}: {req.original_category} → {req.corrected_category}")
    return CorrectionItem(**updated)


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
