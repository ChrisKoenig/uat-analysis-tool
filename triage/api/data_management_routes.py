"""
Data Management API Routes
============================

FR-2005 – REST endpoints for entity export/import.

Endpoints:
    POST /api/v1/data-management/export          - Export selected entities
    POST /api/v1/data-management/import/preview   - Preview an import bundle
    POST /api/v1/data-management/import/execute   - Execute import with auto-backup
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

logger = logging.getLogger("triage.api.data_management")

router = APIRouter(prefix="/api/v1/data-management", tags=["Data Management"])


# =============================================================================
# Request / Response Models
# =============================================================================

class ExportRequest(BaseModel):
    """Which entities to export. Key = entity type, value = list of IDs or null for all."""
    selections: Dict[str, Optional[List[str]]] = Field(
        ...,
        description="Entity types to export. Value is list of IDs (or null for all of that type).",
        examples=[{"rules": None, "triggers": ["dt-abc12345"]}],
    )


class ImportPreviewRequest(BaseModel):
    """The full export bundle to preview."""
    bundle: Dict[str, Any] = Field(..., description="The export JSON bundle")


class ImportExecuteRequest(BaseModel):
    """Execute an import."""
    bundle: Dict[str, Any] = Field(..., description="The export JSON bundle")
    selected: Optional[Dict[str, Optional[List[str]]]] = Field(
        None,
        description="Optional per-type list of entity *names* to import. Null = import all.",
    )


# =============================================================================
# Service Singleton
# =============================================================================

_dm_service = None

def get_dm_service():
    global _dm_service
    if _dm_service is None:
        from ..services.data_management_service import DataManagementService
        _dm_service = DataManagementService()
    return _dm_service


# =============================================================================
# Export
# =============================================================================

@router.post("/export")
async def export_entities(body: ExportRequest):
    """
    Export selected entities with auto-included dependencies.
    Returns a JSON bundle suitable for download.
    """
    try:
        svc = get_dm_service()
        bundle = svc.export_entities(body.selections, actor="api-user")
        return bundle
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Import — Preview
# =============================================================================

@router.post("/import/preview")
async def preview_import(body: ImportPreviewRequest):
    """
    Parse an export bundle and return what would happen without executing.
    Shows per-entity create/update/skip counts.
    """
    try:
        svc = get_dm_service()
        preview = svc.preview_import(body.bundle)
        return preview
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Import preview failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Import — Execute
# =============================================================================

@router.post("/import/execute")
async def execute_import(body: ImportExecuteRequest):
    """
    Execute import with auto-backup, name-based upsert and full audit trail.
    """
    try:
        svc = get_dm_service()
        result = svc.execute_import(body.bundle, body.selected, actor="api-user")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Import execution failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Backups
# =============================================================================

@router.get("/backups")
async def list_backups(limit: int = 20):
    """List persisted pre-import backups (summary only)."""
    try:
        svc = get_dm_service()
        return {"backups": svc.list_backups(limit=limit)}
    except Exception as e:
        logger.exception("List backups failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backups/{audit_id}")
async def get_backup(audit_id: str):
    """Retrieve the full backup bundle for a given audit entry."""
    try:
        svc = get_dm_service()
        bundle = svc.get_backup_for_audit(audit_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail="Backup not found")
        return bundle
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Get backup failed")
        raise HTTPException(status_code=500, detail=str(e))
