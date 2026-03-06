"""
Triage API - FastAPI Application
=================================

Main FastAPI application for the Triage Management System.
Runs on port 8009 alongside the existing microservices.

Endpoints:
    /api/v1/rules      - CRUD for rules
    /api/v1/actions     - CRUD for actions
    /api/v1/triggers    - CRUD for triggers
    /api/v1/routes      - CRUD for routes
    /api/v1/evaluate    - Trigger evaluations
    /api/v1/evaluations - View evaluation history
    /api/v1/audit       - Audit log queries
    /api/v1/validation  - Validation and warnings
    /health             - Health check

All endpoints follow REST conventions:
    GET    /resource        - List (with optional ?status= filter)
    GET    /resource/{id}   - Get single
    POST   /resource        - Create
    PUT    /resource/{id}   - Update (with optimistic locking)
    DELETE /resource/{id}   - Delete (soft by default)
    POST   /resource/{id}/copy - Clone
"""

from typing import Optional
from datetime import datetime, timezone
import logging
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger("triage.api")

# ---------------------------------------------------------------------------
# Application Insights telemetry (opt-in via APPLICATIONINSIGHTS_CONNECTION_STRING)
# ---------------------------------------------------------------------------
try:
    _ai_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if _ai_conn:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=_ai_conn)
        # Suppress verbose Azure SDK HTTP logging (full request/response headers)
        # Telemetry still flows to App Insights — just not to the console.
        for _name in (
            "azure.core.pipeline.policies.http_logging_policy",
            "azure.monitor.opentelemetry.exporter",
            "azure.monitor.opentelemetry.exporter.export",
            "azure.monitor.opentelemetry.exporter.export._base",
            "azure.identity",
            "azure.identity._credentials",
        ):
            logging.getLogger(_name).setLevel(logging.WARNING)
        logger.info("Application Insights enabled for Triage API")
except Exception as _ai_err:
    logger.warning("App Insights init skipped: %s", _ai_err)

from .schemas import (
    RuleCreate, RuleUpdate,
    ActionCreate, ActionUpdate,
    TriggerCreate, TriggerUpdate,
    RouteCreate, RouteUpdate,
    TriageTeamCreate, TriageTeamUpdate,
    EvaluateRequest, EvaluateResponse,
    StatusUpdate, CopyRequest,
    HealthResponse, ErrorResponse, ReferenceResponse,
    TriageQueueRequest, TriageQueueResponse,
    TriageQueueDetailsResponse, QueueItemSummary,
    SavedQueryResponse, SavedQueryItemSummary, QueryColumn,
    ApplyChangesRequest, ApplyChangesResponse,
    WebhookResponse, AdoConnectionStatus,
    AnalyzeRequest, ReanalyzeRequest, AnalysisStateRequest,
)
from ..services.crud_service import CrudService, ConflictError
from ..services.evaluation_service import EvaluationService
from ..services.audit_service import AuditService
from ..services.ado_client import AdoClient, get_ado_client, TriageAdoConfig
from ..services.webhook_receiver import WebhookProcessor, WebhookPayload
from ..config.cosmos_config import get_cosmos_config
from ..models.analysis_result import AnalysisResult


# =============================================================================
# Application Setup
# =============================================================================

app = FastAPI(
    title="Triage Management API",
    description=(
        "REST API for the Triage Management System. "
        "Manages rules, actions, triggers, and routes for "
        "automated ADO Action triage."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS: Allow React frontend on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:5003",  # Existing Flask app
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Mount sub-routers (new platform endpoints)
# =============================================================================

from .classify_routes import router as classify_router
from .admin_routes import router as admin_router
from .data_management_routes import router as data_mgmt_router

app.include_router(classify_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(data_mgmt_router)  # already has /api/v1 prefix


# =============================================================================
# Service Singletons (initialized on first request)
# =============================================================================

_crud_service: Optional[CrudService] = None
_eval_service: Optional[EvaluationService] = None
_audit_service: Optional[AuditService] = None
_ado_client: Optional[AdoClient] = None
_webhook_processor: Optional[WebhookProcessor] = None


def get_crud() -> CrudService:
    """Get or create the CRUD service singleton"""
    global _crud_service
    if _crud_service is None:
        _crud_service = CrudService()
    return _crud_service


def get_eval() -> EvaluationService:
    """Get or create the Evaluation service singleton"""
    global _eval_service
    if _eval_service is None:
        _eval_service = EvaluationService()
    return _eval_service


def get_audit() -> AuditService:
    """Get or create the Audit service singleton"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service


def get_ado() -> AdoClient:
    """
    Get or create the ADO client singleton.
    
    Lazy-initialized on first use. If ADO credentials are not
    available, this will raise — callers should handle gracefully.
    """
    global _ado_client
    if _ado_client is None:
        _ado_client = get_ado_client()
    return _ado_client


def get_webhook() -> WebhookProcessor:
    """Get or create the Webhook processor singleton"""
    global _webhook_processor
    if _webhook_processor is None:
        _webhook_processor = WebhookProcessor()
    return _webhook_processor


# =============================================================================
# Health Check
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Service health check.
    
    Returns service status and Cosmos DB connection health.
    """
    try:
        cosmos = get_cosmos_config()
        db_health = cosmos.health_check()
    except Exception as e:
        db_health = {"status": "error", "error": str(e)}
    
    # API is always "healthy" if it can respond; database may be degraded
    api_status = "healthy" if db_health.get("status") == "healthy" else "degraded"
    return HealthResponse(
        status=api_status,
        service="triage-api",
        version="1.0.0",
        database=db_health
    )


# =============================================================================
# Generic CRUD Endpoint Factory
# =============================================================================
# Since rules, actions, triggers, and routes all follow the same CRUD pattern,
# we create a helper that builds all endpoints for an entity type.

def _create_crud_endpoints(entity_type: str, create_model, update_model):
    """
    Create standard CRUD endpoints for an entity type.
    
    Registers:
        GET    /api/v1/{entity_type}s         - List
        GET    /api/v1/{entity_type}s/{id}    - Get
        POST   /api/v1/{entity_type}s         - Create
        PUT    /api/v1/{entity_type}s/{id}    - Update
        DELETE /api/v1/{entity_type}s/{id}    - Delete
        POST   /api/v1/{entity_type}s/{id}/copy    - Copy
        PUT    /api/v1/{entity_type}s/{id}/status  - Status change
        GET    /api/v1/{entity_type}s/{id}/references - Cross-references
    """
    plural = f"{entity_type}s"
    tag = entity_type.capitalize() + "s"
    
    # --- LIST ---
    @app.get(f"/api/v1/{plural}", tags=[tag])
    async def list_entities(
        status: Optional[str] = Query(None, description="Filter by status"),
        triage_team_id: Optional[str] = Query(None, description="Filter by triage team ID (or 'all' for shared)"),
    ):
        """List entities with optional status and triage team filter.
        Returns empty results when Cosmos DB is unavailable (graceful degradation)."""
        try:
            crud = get_crud()
            items, token = crud.list(entity_type, status=status)
            # Client-side filter by triageTeamId if requested
            if triage_team_id is not None and entity_type not in ("triage-team",):
                if triage_team_id == "all":
                    # Only items scoped to ALL teams (no triageTeamId)
                    items = [i for i in items if not i.get("triageTeamId")]
                else:
                    # Items scoped to the specific team OR available to all
                    items = [i for i in items if not i.get("triageTeamId") or i.get("triageTeamId") == triage_team_id]
            return {
                "items": items,
                "count": len(items),
                "continuationToken": token,
            }
        except Exception as e:
            # Graceful degradation: return empty results instead of 500
            # so the UI can still render with empty state
            logger.warning("%s list unavailable (Cosmos offline): %s", tag, e)
            return {
                "items": [],
                "count": 0,
                "continuationToken": None,
                "warning": f"Data unavailable: {str(e)}",
            }
    
    # Give the function a unique name for FastAPI's route registry
    list_entities.__name__ = f"list_{plural}"
    list_entities.__qualname__ = f"list_{plural}"
    
    # --- GET ---
    @app.get(f"/api/v1/{plural}/{{entity_id}}", tags=[tag])
    async def get_entity(entity_id: str):
        """Get a single entity by ID"""
        crud = get_crud()
        item = crud.get(entity_type, entity_id)
        if item is None:
            raise HTTPException(
                status_code=404,
                detail=f"{entity_type} '{entity_id}' not found"
            )
        return item
    
    get_entity.__name__ = f"get_{entity_type}"
    get_entity.__qualname__ = f"get_{entity_type}"
    
    # --- CREATE ---
    @app.post(f"/api/v1/{plural}", status_code=201, tags=[tag])
    async def create_entity(body: create_model):
        """Create a new entity"""
        try:
            crud = get_crud()
            data = body.model_dump(exclude_none=True)
            result = crud.create(entity_type, data, actor="api-user")
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    create_entity.__name__ = f"create_{entity_type}"
    create_entity.__qualname__ = f"create_{entity_type}"
    
    # --- UPDATE ---
    @app.put(f"/api/v1/{plural}/{{entity_id}}", tags=[tag])
    async def update_entity(entity_id: str, body: update_model):
        """Update an existing entity (requires version for optimistic locking)"""
        try:
            crud = get_crud()
            data = body.model_dump(exclude_none=True)
            result = crud.update(entity_type, entity_id, data, actor="api-user")
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ConflictError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    update_entity.__name__ = f"update_{entity_type}"
    update_entity.__qualname__ = f"update_{entity_type}"
    
    # --- DELETE ---
    @app.delete(f"/api/v1/{plural}/{{entity_id}}", tags=[tag])
    async def delete_entity(
        entity_id: str,
        hard: bool = Query(False, description="Permanently delete"),
        version: Optional[int] = Query(
            None, description="Expected version for optimistic locking"
        ),
    ):
        """Delete an entity (soft delete by default, ?hard=true for permanent).
        Blocks deletion if the entity is still referenced by other entities."""
        try:
            crud = get_crud()
            crud.delete(
                entity_type, entity_id,
                actor="api-user", hard_delete=hard, version=version
            )
            return {"status": "deleted", "id": entity_id, "hard": hard}
        except ValueError as e:
            # Includes "still referenced" errors
            raise HTTPException(status_code=400, detail=str(e))
        except ConflictError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    delete_entity.__name__ = f"delete_{entity_type}"
    delete_entity.__qualname__ = f"delete_{entity_type}"
    
    # --- COPY ---
    @app.post(f"/api/v1/{plural}/{{entity_id}}/copy", status_code=201, tags=[tag])
    async def copy_entity(entity_id: str, body: CopyRequest = CopyRequest()):
        """Clone an entity with a new ID"""
        try:
            crud = get_crud()
            result = crud.copy(
                entity_type, entity_id,
                actor="api-user",
                new_name=body.newName
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    copy_entity.__name__ = f"copy_{entity_type}"
    copy_entity.__qualname__ = f"copy_{entity_type}"
    
    # --- STATUS ---
    @app.put(f"/api/v1/{plural}/{{entity_id}}/status", tags=[tag])
    async def update_status(entity_id: str, body: StatusUpdate):
        """Change entity status (active/disabled/staged).\n        Requires version for optimistic locking."""
        try:
            crud = get_crud()
            result = crud.set_status(
                entity_type, entity_id, body.status,
                actor="api-user", version=body.version
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ConflictError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    update_status.__name__ = f"update_{entity_type}_status"
    update_status.__qualname__ = f"update_{entity_type}_status"
    
    # --- REFERENCES ---
    @app.get(f"/api/v1/{plural}/{{entity_id}}/references", tags=[tag])
    async def get_references(entity_id: str):
        """Get cross-references (which entities use this one).
        Returns empty refs when Cosmos DB is unavailable.
        Includes referenceNames map for friendly display."""
        try:
            crud = get_crud()
            refs = crud.find_references(entity_type, entity_id)

            # Build name lookup for referenced entity IDs
            ref_names = {}
            try:
                cosmos = get_cosmos_config()
                for ref_type, ref_ids in refs.items():
                    container_name = ref_type  # e.g. "triggers", "routes"
                    container = cosmos.get_container(container_name)
                    for doc in container.query_items(
                        query="SELECT c.id, c.name FROM c",
                        enable_cross_partition_query=True,
                    ):
                        if doc["id"] in ref_ids:
                            ref_names[doc["id"]] = doc.get("name", doc["id"])
            except Exception:
                pass  # Non-fatal

            return {
                "entityType": entity_type,
                "entityId": entity_id,
                "references": refs,
                "referenceNames": ref_names,
            }
        except Exception as e:
            logger.warning("References unavailable (Cosmos offline): %s", e)
            return {"entityType": entity_type, "entityId": entity_id,
                    "references": [], "referenceNames": {}, "warning": str(e)}
    
    get_references.__name__ = f"get_{entity_type}_references"
    get_references.__qualname__ = f"get_{entity_type}_references"


# =============================================================================
# Register CRUD Endpoints for All Entity Types
# =============================================================================

_create_crud_endpoints("rule", RuleCreate, RuleUpdate)
_create_crud_endpoints("action", ActionCreate, ActionUpdate)
_create_crud_endpoints("trigger", TriggerCreate, TriggerUpdate)
_create_crud_endpoints("route", RouteCreate, RouteUpdate)
_create_crud_endpoints("triage-team", TriageTeamCreate, TriageTeamUpdate)


# =============================================================================
# Evaluation Endpoints
# =============================================================================

@app.post("/api/v1/evaluate", tags=["Evaluation"])
async def evaluate(body: EvaluateRequest):
    """
    Evaluate one or more work items through the triage pipeline.
    
    Pipeline:
        1. Fetch work item data from ADO (via AdoClient)
        2. Run rules engine → T/F per rule
        3. Walk triggers → find first matching trigger
        4. Compute route actions → planned field changes
        5. Store evaluation record in Cosmos DB
        6. Return evaluation results (does NOT auto-apply to ADO)
    
    Use POST /api/v1/evaluate/apply to write changes back to ADO
    after reviewing the evaluation results.
    """
    try:
        ado = get_ado()
        eval_service = get_eval()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service initialization failed: {str(e)}"
        )
    
    results = []
    errors = []
    
    # Fetch work items from ADO
    if len(body.workItemIds) == 1:
        # Single item — use get_work_item for simpler response
        ado_result = ado.get_work_item(body.workItemIds[0])
        if ado_result["success"]:
            items_data = [{
                "id": ado_result["id"],
                "rev": ado_result["rev"],
                "fields": ado_result["fields"],
            }]
        else:
            raise HTTPException(
                status_code=404,
                detail=ado_result.get("error", "Work item not found")
            )
    else:
        # Batch fetch
        batch_result = ado.get_work_items_batch(body.workItemIds)
        if not batch_result["success"]:
            raise HTTPException(
                status_code=502,
                detail=batch_result.get("error", "Failed to fetch work items")
            )
        items_data = batch_result["items"]
        
        # Report any individual failures
        for failed_id in batch_result.get("failed_ids", []):
            errors.append(f"Failed to fetch work item {failed_id}")
    
    # Build ID → name lookup maps for friendly display
    rule_name_map = {}
    trigger_name_map = {}
    route_name_map = {}
    action_name_map = {}
    try:
        cosmos = get_cosmos_config()
        for rdoc in cosmos.get_container("rules").query_items(
            query="SELECT c.id, c.name FROM c",
            enable_cross_partition_query=True,
        ):
            rule_name_map[rdoc["id"]] = rdoc.get("name", rdoc["id"])
        for tdoc in cosmos.get_container("triggers").query_items(
            query="SELECT c.id, c.name FROM c",
            enable_cross_partition_query=True,
        ):
            trigger_name_map[tdoc["id"]] = tdoc.get("name", tdoc["id"])
        for rtdoc in cosmos.get_container("routes").query_items(
            query="SELECT c.id, c.name FROM c",
            enable_cross_partition_query=True,
        ):
            route_name_map[rtdoc["id"]] = rtdoc.get("name", rtdoc["id"])
        for adoc in cosmos.get_container("actions").query_items(
            query="SELECT c.id, c.name FROM c",
            enable_cross_partition_query=True,
        ):
            action_name_map[adoc["id"]] = adoc.get("name", adoc["id"])
    except Exception:
        pass  # Non-fatal — frontend will fall back to raw IDs

    # Run evaluation pipeline for each item
    for item in items_data:
        work_item_id = item["id"]
        fields = item["fields"]
        
        # Look up existing analysis from Cosmos (if available)
        analysis_obj = None
        try:
            analysis_container = get_cosmos_config().get_container("analysis-results")
            analysis_docs = list(analysis_container.query_items(
                query="SELECT * FROM c WHERE c.workItemId = @wid ORDER BY c.timestamp DESC OFFSET 0 LIMIT 1",
                parameters=[{"name": "@wid", "value": work_item_id}],
                partition_key=work_item_id,
            ))
            if analysis_docs:
                analysis_obj = AnalysisResult.from_dict(analysis_docs[0])
        except Exception:
            pass  # Non-fatal — rules will skip Analysis.* conditions
        
        evaluation = eval_service.evaluate(
            work_item_id=work_item_id,
            work_item_data=fields,
            analysis=analysis_obj,
            actor="api-user",
            dry_run=body.dryRun,
        )
        
        results.append({
            "id": evaluation.id,
            "workItemId": work_item_id,
            "analysisState": evaluation.analysisState,
            "matchedTrigger": evaluation.matchedTrigger,
            "appliedRoute": evaluation.appliedRoute,
            "actionsExecuted": evaluation.actionsExecuted,
            "ruleResults": evaluation.ruleResults,
            "ruleNames": rule_name_map,
            "triggerNames": trigger_name_map,
            "routeNames": route_name_map,
            "actionNames": action_name_map,
            "fieldsChanged": evaluation.fieldsChanged,
            "errors": evaluation.errors,
            "isDryRun": evaluation.isDryRun,
            "summaryHtml": evaluation.summaryHtml,
            "adoLink": ado.get_work_item_link(work_item_id),
        })
    
    return {
        "evaluations": results,
        "count": len(results),
        "errors": errors,
    }


@app.post("/api/v1/evaluate/test", tags=["Evaluation"])
async def evaluate_test(body: EvaluateRequest):
    """
    Dry run evaluation - computes results without writing to ADO.
    Equivalent to evaluate with dryRun=True.
    """
    body.dryRun = True
    return await evaluate(body)


@app.post("/api/v1/evaluate/apply", tags=["Evaluation"])
async def apply_evaluation(body: ApplyChangesRequest):
    """
    Apply evaluation results to ADO.
    
    Takes an evaluation ID and writes the computed field changes
    back to the ADO work item. This is the "commit" step after
    human review of evaluation results.
    
    Conflict handling:
        If a revision number is provided and doesn't match the
        current work item revision, returns 409 Conflict.
    """
    try:
        ado = get_ado()
        eval_service = get_eval()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service initialization failed: {str(e)}"
        )
    
    # Fetch the evaluation record from Cosmos DB
    try:
        history = eval_service.get_evaluation_history(
            body.workItemId, limit=50
        )
        evaluation_data = None
        for entry in history:
            if entry.get("id") == body.evaluationId:
                evaluation_data = entry
                break
        
        if not evaluation_data:
            raise HTTPException(
                status_code=404,
                detail=f"Evaluation '{body.evaluationId}' not found"
            )
        
        # Block applying dry-run evaluations to ADO.
        # Dry runs are for testing only — promote to a live evaluation first.
        if evaluation_data.get("isDryRun", False):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Evaluation '{body.evaluationId}' is a dry-run result "
                    f"and cannot be applied to ADO. Run a live evaluation "
                    f"to produce committable results."
                )
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching evaluation: {str(e)}"
        )
    
    # Build field changes from the stored evaluation
    fields_changed = evaluation_data.get("fieldsChanged", {})
    if not fields_changed:
        return ApplyChangesResponse(
            success=True,
            workItemId=body.workItemId,
            fieldsUpdated=0,
            error="No field changes in this evaluation",
        )
    
    # Create lightweight change objects for the ADO client
    class _Change:
        def __init__(self, field, new_value):
            self.field = field
            self.new_value = new_value
    
    changes = [
        _Change(field, change_data.get("to"))
        for field, change_data in fields_changed.items()
        # Skip Discussion field — that's handled via add_comment
        if field != "Discussion"
    ]
    
    # Apply field changes to ADO
    update_result = ado.update_work_item(
        body.workItemId, changes, revision=body.revision
    )
    
    if not update_result["success"]:
        if update_result.get("conflict"):
            raise HTTPException(
                status_code=409,
                detail=update_result.get("error", "Conflict")
            )
        raise HTTPException(
            status_code=502,
            detail=update_result.get("error", "ADO update failed")
        )
    
    # Post discussion comment if HTML summary exists
    comment_posted = False
    summary_html = evaluation_data.get("summaryHtml")
    if summary_html:
        comment_result = ado.add_comment(body.workItemId, summary_html)
        comment_posted = comment_result.get("success", False)
    
    # If there's a Discussion field change (e.g., @ping comment), post that too
    discussion_change = fields_changed.get("Discussion")
    if discussion_change and discussion_change.get("to"):
        ping_result = ado.add_comment(
            body.workItemId, discussion_change["to"]
        )
        if ping_result.get("success"):
            comment_posted = True
    
    return ApplyChangesResponse(
        success=True,
        workItemId=body.workItemId,
        fieldsUpdated=len(changes),
        commentPosted=comment_posted,
        newRevision=update_result.get("rev"),
    )


@app.get("/api/v1/evaluations/{work_item_id}", tags=["Evaluation"])
async def get_evaluations(work_item_id: int, limit: int = 20):
    """Get evaluation history for a specific work item"""
    try:
        eval_service = get_eval()
        history = eval_service.get_evaluation_history(
            work_item_id, limit=limit
        )
        return {"workItemId": work_item_id, "evaluations": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Analysis Result Endpoints
# =============================================================================

@app.get("/api/v1/analysis/batch", tags=["Analysis"])
async def get_analysis_batch(
    ids: str = Query(..., description="Comma-separated work item IDs"),
):
    """
    Batch lookup of analysis results for multiple work items.

    Returns a dict keyed by workItemId with summary fields
    (category, intent, confidence, timestamp) for items that have
    analysis results.  Items without analysis are omitted.
    """
    try:
        work_item_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="ids must be comma-separated integers")

    if not work_item_ids:
        return {"results": {}}

    cosmos = get_cosmos_config()
    container = cosmos.get_container("analysis-results")
    results: dict = {}

    for wid in work_item_ids:
        try:
            # Query by partition key for efficiency
            query = (
                "SELECT c.id, c.workItemId, c.timestamp, c.category, "
                "c.intent, c.confidence, c.source, c.businessImpact, "
                "c.urgencyLevel "
                "FROM c WHERE c.workItemId = @wid "
                "ORDER BY c.timestamp DESC OFFSET 0 LIMIT 1"
            )
            items = list(container.query_items(
                query=query,
                parameters=[{"name": "@wid", "value": wid}],
                partition_key=wid,
            ))
            if items:
                doc = items[0]
                results[str(wid)] = {
                    "id": doc.get("id", ""),
                    "workItemId": wid,
                    "category": doc.get("category", ""),
                    "intent": doc.get("intent", ""),
                    "confidence": doc.get("confidence", 0.0),
                    "source": doc.get("source", ""),
                    "businessImpact": doc.get("businessImpact", ""),
                    "urgencyLevel": doc.get("urgencyLevel", ""),
                    "timestamp": doc.get("timestamp", ""),
                }
        except Exception:
            # Skip items that fail (e.g., partition not found)
            continue

    return {"results": results}


@app.get("/api/v1/analysis/{work_item_id}", tags=["Analysis"])
async def get_analysis_detail(work_item_id: int):
    """
    Get the full latest analysis result for a work item.

    Returns all fields from the AnalysisResult model,
    or 404 if no analysis exists.
    """
    cosmos = get_cosmos_config()
    container = cosmos.get_container("analysis-results")

    try:
        query = (
            "SELECT * FROM c WHERE c.workItemId = @wid "
            "ORDER BY c.timestamp DESC OFFSET 0 LIMIT 1"
        )
        items = list(container.query_items(
            query=query,
            parameters=[{"name": "@wid", "value": work_item_id}],
            partition_key=work_item_id,
        ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for work item {work_item_id}",
        )

    return items[0]


# -- PATCH: Update ServiceTree routing fields on a single analysis record ------

class _RoutingPatch(BaseModel):
    """Allowed fields for inline routing override."""
    serviceTreeMatch: Optional[str] = None
    serviceTreeOffering: Optional[str] = None
    solutionArea: Optional[str] = None
    csuDri: Optional[str] = None
    areaPathAdo: Optional[str] = None
    releaseManager: Optional[str] = None
    devContact: Optional[str] = None


@app.patch("/api/v1/analysis/{work_item_id}/routing", tags=["Analysis"])
async def patch_analysis_routing(work_item_id: int, patch: _RoutingPatch):
    """
    Update ServiceTree routing fields on the latest analysis record.
    Only non-null fields in the request body are applied.
    """
    cosmos = get_cosmos_config()
    container = cosmos.get_container("analysis-results")

    # Fetch latest analysis
    try:
        query = (
            "SELECT * FROM c WHERE c.workItemId = @wid "
            "ORDER BY c.timestamp DESC OFFSET 0 LIMIT 1"
        )
        items = list(container.query_items(
            query=query,
            parameters=[{"name": "@wid", "value": work_item_id}],
            partition_key=work_item_id,
        ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not items:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for work item {work_item_id}",
        )

    doc = items[0]
    updates = {k: v for k, v in patch.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in updates.items():
        doc[field] = value

    # Stamp override metadata
    doc["routingOverrideBy"] = "admin"
    doc["routingOverrideAt"] = datetime.now(timezone.utc).isoformat()

    try:
        container.upsert_item(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    logger.info("Routing override applied for WI %s: %s", work_item_id, updates)
    return {
        "status": "updated",
        "workItemId": work_item_id,
        "updatedFields": updates,
    }


# -- Analyzer singleton (lazy init — may require Azure OpenAI config) ---------
_analyzer = None

def get_analyzer():
    """Get or create the HybridContextAnalyzer singleton."""
    global _analyzer
    if _analyzer is None:
        import sys, os
        # Add workspace root so top-level modules are importable
        workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if workspace_root not in sys.path:
            sys.path.insert(0, workspace_root)
        from hybrid_context_analyzer import HybridContextAnalyzer
        _analyzer = HybridContextAnalyzer(use_ai=True)
    return _analyzer


def _map_hybrid_to_analysis_result(
    work_item_id: int, hybrid_result, title: str, description: str,
) -> AnalysisResult:
    """Map HybridAnalysisResult → AnalysisResult for Cosmos storage."""
    from ..models.base import utc_now
    from enum import Enum
    import datetime

    def _enum_val(v):
        """Extract .value from enums, otherwise str()."""
        if isinstance(v, Enum):
            return v.value
        return v if isinstance(v, str) else str(v) if v else ""

    ts = utc_now()
    date_str = datetime.datetime.utcnow().strftime("%Y%m%d")

    # Extract domain_entities dict from hybrid result (azure_services, regions, etc.)
    _de = getattr(hybrid_result, "domain_entities", None) or {}

    detected_products = [
        p.get("name", str(p)) if isinstance(p, dict) else str(p)
        for p in (getattr(hybrid_result, "pattern_features", {}) or {}).get("detected_products", [])
    ]
    azure_services = _de.get("azure_services", [])

    # ── ServiceTree enrichment ───────────────────────────────────────────
    st_match = st_offering = sol_area = csu_dri = ""
    area_path_ado = release_mgr = dev_contact = ""
    try:
        import sys
        _proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if _proj_root not in sys.path:
            sys.path.insert(0, _proj_root)
        from servicetree_service import get_servicetree_service

        svc = get_servicetree_service()
        # Combine detected products + azure services for best-effort lookup
        lookup_names = detected_products + azure_services
        best = svc.get_best_match(lookup_names)
        if best:
            st_match = best.get("name", "")
            st_offering = best.get("offeringName", "")
            sol_area = best.get("solutionAreaGcs", "")
            csu_dri = best.get("csuDri", "")
            area_path_ado = best.get("areaPathAdo", "")
            release_mgr = best.get("releaseManager", "")
            dev_contact = best.get("devContact", "")
            logger.info(
                "ServiceTree match for WI %s: %s → %s (%s)",
                work_item_id, lookup_names[:3], st_match, sol_area,
            )
    except Exception as st_err:
        logger.warning("ServiceTree enrichment skipped for WI %s: %s", work_item_id, st_err)

    return AnalysisResult(
        id=f"analysis-{work_item_id}-{date_str}",
        workItemId=work_item_id,
        timestamp=ts,
        originalTitle=title,
        originalDescription=description[:500] if description else "",
        category=_enum_val(getattr(hybrid_result, "category", "")),
        intent=_enum_val(getattr(hybrid_result, "intent", "")),
        confidence=getattr(hybrid_result, "confidence", 0.0),
        source=_enum_val(getattr(hybrid_result, "source", "pattern")),
        agreement=getattr(hybrid_result, "agreement", False),
        businessImpact=getattr(hybrid_result, "business_impact", ""),
        technicalComplexity=getattr(hybrid_result, "technical_complexity", "") or "",
        urgencyLevel=getattr(hybrid_result, "urgency_level", "") or "",
        detectedProducts=detected_products,
        azureServices=azure_services,
        complianceFrameworks=_de.get("compliance_frameworks", []),
        technologies=_de.get("technologies", []),
        regions=_de.get("regions", []),
        businessDomains=_de.get("business_domains", []),
        technicalAreas=_de.get("technical_areas", []),
        discoveredServices=_de.get("discovered_services", []),
        # ServiceTree routing
        serviceTreeMatch=st_match,
        serviceTreeOffering=st_offering,
        solutionArea=sol_area,
        csuDri=csu_dri,
        areaPathAdo=area_path_ado,
        releaseManager=release_mgr,
        devContact=dev_contact,
        keyConcepts=getattr(hybrid_result, "key_concepts", None) or [],
        semanticKeywords=getattr(hybrid_result, "semantic_keywords", None) or [],
        contextSummary=getattr(hybrid_result, "context_summary", "") or "",
        reasoning=str(getattr(hybrid_result, "reasoning", "")),
        patternCategory=_enum_val(getattr(hybrid_result, "pattern_category", "")),
        patternConfidence=getattr(hybrid_result, "pattern_confidence", 0.0),
        aiAvailable=getattr(hybrid_result, "ai_available", True),
        aiError=getattr(hybrid_result, "ai_error", None),
    )


@app.get("/api/v1/analyze/status", tags=["Analysis"])
async def get_analysis_engine_status():
    """Check whether the analysis engine and AI services are available."""
    try:
        analyzer = get_analyzer()
        return {
            "available": True,
            "aiAvailable": getattr(analyzer, "use_ai", False),
            "mode": "AI-Powered" if getattr(analyzer, "use_ai", False) else "Pattern Only",
        }
    except Exception as e:
        return {
            "available": False,
            "aiAvailable": False,
            "mode": "Unavailable",
            "error": str(e),
        }


# ── Graph User Lookup (FR-1998) ──────────────────────────────────────────

@app.get("/api/v1/graph/user", tags=["Graph"])
async def get_graph_user(email: str):
    """
    Look up user info from Microsoft Graph by email/UPN.

    Returns displayName, jobTitle, and department for the given user.
    The email can be a bare address (user@domain.com) or an ADO-style
    identity string like "Display Name <user@domain.com>".
    """
    import re as _re
    from graph_user_lookup import get_user_info

    # Normalise ADO identity strings: "Display Name <email>" → email
    clean = email.strip()
    m = _re.search(r"<([^>]+)>", clean)
    if m:
        clean = m.group(1)

    info = get_user_info(clean)
    if not info:
        raise HTTPException(status_code=404, detail=f"User not found: {clean}")

    return {
        "displayName": info.display_name,
        "jobTitle": info.job_title,
        "department": info.department,
        "email": clean,
    }


@app.get("/api/v1/diagnostics", tags=["Health"])
async def get_diagnostics():
    """
    Lightweight diagnostics endpoint for the debug panel.

    Returns service connectivity status for each subsystem so a user
    can copy/paste the output for troubleshooting without exposing secrets.
    Each sub-check has a 5 s timeout so the endpoint always returns quickly.
    """
    import asyncio
    import time as _time

    CHECK_TIMEOUT = 5          # seconds per subsystem
    AI_INIT_TIMEOUT = 15       # first-time analyzer init can be slow

    diag = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api": {"status": "healthy"},
        "cosmos": {},
        "ai": {},
        "ado": {},
    }

    # --- Cosmos DB ---
    def _check_cosmos():
        t0 = _time.perf_counter()
        cosmos = get_cosmos_config()
        info = cosmos.health_check()
        ms = int((_time.perf_counter() - t0) * 1000)
        st = info.get("status", "healthy")
        # Normalise "healthy (in-memory)" → "healthy" with a note
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
        analyzer = get_analyzer()          # lazy-init singleton on first call
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
        diag["ai"] = {"status": "timeout", "error": f"AI check exceeded {CHECK_TIMEOUT}s"}
    except Exception as e:
        diag["ai"] = {"status": "error", "error": str(e)}

    # --- ADO ---
    def _check_ado():
        t0 = _time.perf_counter()
        from ..services.ado_client import get_ado_client
        _ado = get_ado_client()
        ms = int((_time.perf_counter() - t0) * 1000)
        return {"status": "healthy", "latencyMs": ms}

    try:
        diag["ado"] = await asyncio.wait_for(
            asyncio.to_thread(_check_ado), timeout=CHECK_TIMEOUT
        )
    except asyncio.TimeoutError:
        diag["ado"] = {"status": "timeout", "error": f"Health check exceeded {CHECK_TIMEOUT}s"}
    except Exception as e:
        diag["ado"] = {"status": "error", "error": str(e)}

    return diag


def _mask_url(url: str) -> str:
    """Mask the middle of a URL for safe display (no full endpoint exposure)."""
    if not url:
        return "(not configured)"
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        parts = host.split(".")
        if len(parts) > 2:
            parts[0] = parts[0][:4] + "***"
        return f"{parsed.scheme}://{'.'.join(parts)}"
    except Exception:
        return url[:12] + "***"


@app.post("/api/v1/analyze", tags=["Analysis"])
async def run_analysis(body: AnalyzeRequest):
    """
    Run the hybrid analysis engine on one or more work items.

    Fetches title/description from ADO, runs pattern + LLM analysis,
    stores the AnalysisResult in Cosmos, and returns summaries.
    """
    try:
        ado = get_ado()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ADO connection failed: {e}")

    try:
        analyzer = get_analyzer()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Analysis engine failed to initialize: {e}",
        )

    cosmos = get_cosmos_config()
    container = cosmos.get_container("analysis-results")

    results = []
    errors = []

    # Fetch work items from ADO
    if len(body.workItemIds) == 1:
        ado_result = ado.get_work_item(body.workItemIds[0])
        if ado_result["success"]:
            items_data = [{
                "id": ado_result["id"],
                "fields": ado_result["fields"],
            }]
        else:
            raise HTTPException(status_code=404, detail="Work item not found")
    else:
        batch = ado.get_work_items_batch(body.workItemIds)
        if not batch["success"]:
            raise HTTPException(status_code=502, detail="Batch fetch failed")
        items_data = batch["items"]
        for fid in batch.get("failed_ids", []):
            errors.append(f"Failed to fetch #{fid}")

    # Analyze each item
    for item in items_data:
        wid = item["id"]
        fields = item.get("fields", {})
        title = fields.get("System.Title", "")
        description = fields.get("System.Description", "")
        # Strip HTML tags from description (ADO descriptions contain HTML)
        import re
        clean_desc = re.sub(r"<[^>]+>", " ", description or "").strip()

        try:
            hybrid_result = analyzer.analyze(title, clean_desc)
            analysis = _map_hybrid_to_analysis_result(wid, hybrid_result, title, clean_desc)

            # Store in Cosmos
            container.upsert_item(analysis.to_dict())

            results.append({
                "workItemId": wid,
                "category": analysis.category,
                "intent": analysis.intent,
                "confidence": analysis.confidence,
                "source": analysis.source,
                "businessImpact": analysis.businessImpact,
                "urgencyLevel": analysis.urgencyLevel,
                "success": True,
            })
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            logger.error("Analysis failed for %s: %s\n%s", wid, e, tb_str)
            errors.append(f"Analysis failed for #{wid}: {str(e)}")
            results.append({
                "workItemId": wid,
                "success": False,
                "error": str(e),
            })

    return {
        "results": results,
        "count": len(results),
        "errors": errors,
    }


@app.post("/api/v1/analyze/reanalyze", tags=["Analysis"])
async def reanalyze_with_corrections(body: ReanalyzeRequest):
    """
    Re-analyze a single work item with user-supplied correction hints.

    Fetches the item from ADO, appends correction context to the description,
    re-runs the HybridContextAnalyzer, stores in Cosmos, and returns the
    updated analysis detail.
    """
    try:
        ado = get_ado()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ADO connection failed: {e}")

    try:
        analyzer = get_analyzer()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Analysis engine failed: {e}")

    # Fetch work item from ADO
    ado_result = ado.get_work_item(body.workItemId)
    if not ado_result.get("success"):
        raise HTTPException(status_code=404, detail=f"Work item {body.workItemId} not found")

    fields = ado_result.get("fields", {})
    title = fields.get("System.Title", "")
    description = fields.get("System.Description", "")
    import re as _re
    clean_desc = _re.sub(r"<[^>]+>", " ", description or "").strip()

    # Build enhanced description with correction hints
    correction_hints = []
    if body.correct_category:
        correction_hints.append(f"[CORRECTION: Category should be {body.correct_category}]")
    if body.correct_intent:
        correction_hints.append(f"[CORRECTION: Intent should be {body.correct_intent}]")
    if body.correct_business_impact:
        correction_hints.append(f"[CORRECTION: Business impact should be {body.correct_business_impact}]")
    if body.correction_notes:
        correction_hints.append(f"[USER NOTE: {body.correction_notes}]")

    enhanced_desc = clean_desc
    if correction_hints:
        enhanced_desc += "\n\n" + "\n".join(correction_hints)

    try:
        hybrid_result = analyzer.analyze(title, enhanced_desc)
        analysis = _map_hybrid_to_analysis_result(body.workItemId, hybrid_result, title, clean_desc)

        # Store updated result in Cosmos
        cosmos = get_cosmos_config()
        container = cosmos.get_container("analysis-results")
        container.upsert_item(analysis.to_dict())

        return {
            "success": True,
            "workItemId": body.workItemId,
            "analysis": analysis.to_dict(),
            "message": "Re-analysis complete with corrections applied.",
        }
    except Exception as e:
        import traceback
        logger.error("Re-analysis failed for %s: %s\n%s", body.workItemId, e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Re-analysis failed: {e}")


@app.post("/api/v1/ado/analysis-state", tags=["ADO"])
async def update_analysis_state(body: AnalysisStateRequest):
    """
    Update Custom.ROBAnalysisState on one or more ADO work items.

    Used to move items between workflow stages:
      Analysis → 'Awaiting Approval' (ready for triage)
      Triage → 'Approved' (triaged)
      Return → 'Pending' (back to analysis)
    """
    VALID_STATES = {
        "Approved", "Awaiting Approval", "Needs Info",
        "No Match", "Override", "Pending", "Redirected",
    }
    if body.state not in VALID_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state '{body.state}'. Valid: {sorted(VALID_STATES)}",
        )

    try:
        ado = get_ado()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ADO connection failed: {e}")

    results = []
    errors = []
    for wid in body.workItemIds:
        try:
            result = ado.set_analysis_state(wid, body.state)
            if result.get("success"):
                results.append({"workItemId": wid, "success": True, "newRev": result.get("rev")})
            else:
                errors.append(f"#{wid}: {result.get('error', 'unknown error')}")
                results.append({"workItemId": wid, "success": False, "error": result.get("error")})
        except Exception as e:
            errors.append(f"#{wid}: {str(e)}")
            results.append({"workItemId": wid, "success": False, "error": str(e)})

    return {"results": results, "count": len(results), "errors": errors}


# =============================================================================
# ADO Integration Endpoints
# =============================================================================

@app.get("/api/v1/ado/queue", tags=["ADO"])
async def get_triage_queue(
    state: Optional[str] = Query(None, description="Filter by ROBAnalysisState"),
    area_path: Optional[str] = Query(None, description="Filter by area path"),
    max_results: int = Query(100, ge=1, le=500),
):
    """
    Fetch the triage queue from ADO.
    
    Returns work item IDs from ADO that are pending triage,
    filtered by analysis state and/or area path.
    """
    try:
        ado = get_ado()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"ADO connection failed: {str(e)}"
        )
    
    result = ado.query_triage_queue(
        state_filter=state,
        area_path=area_path,
        max_results=max_results,
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=502,
            detail=result.get("error", "Queue query failed")
        )
    
    return TriageQueueResponse(
        workItemIds=result["work_item_ids"],
        count=result["count"],
        totalAvailable=result.get("total_available"),
    )


@app.get("/api/v1/ado/queue/details", tags=["ADO"])
async def get_triage_queue_details(
    state: Optional[str] = Query(None, description="Filter by ROBAnalysisState"),
    area_path: Optional[str] = Query(None, description="Filter by area path"),
    max_results: int = Query(100, ge=1, le=500),
):
    """
    Fetch the triage queue from ADO with hydrated item details.

    Combines queue query + batch work item fetch in a single call.
    Returns key fields (title, state, area path, etc.) for each item
    so the UI can display a rich queue table without extra round-trips.
    """
    try:
        ado = get_ado()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"ADO connection failed: {str(e)}"
        )

    # Step 1: Query for work item IDs
    queue_result = ado.query_triage_queue(
        state_filter=state,
        area_path=area_path,
        max_results=max_results,
    )

    if not queue_result["success"]:
        raise HTTPException(
            status_code=502,
            detail=queue_result.get("error", "Queue query failed")
        )

    work_item_ids = queue_result["work_item_ids"]
    if not work_item_ids:
        return TriageQueueDetailsResponse(
            items=[],
            count=0,
            totalAvailable=queue_result.get("total_available", 0),
        )

    # Step 2: Batch-fetch full work item data
    batch_result = ado.get_work_items_batch(work_item_ids)

    items = []
    for item in batch_result.get("items", []):
        fields = item.get("fields", {})
        # Extract assigned-to display name from identity object or string
        assigned_raw = fields.get("System.AssignedTo", "")
        assigned_to = (
            assigned_raw.get("displayName", "")
            if isinstance(assigned_raw, dict)
            else str(assigned_raw)
        )

        items.append(QueueItemSummary(
            id=item["id"],
            rev=item.get("rev", 0),
            title=fields.get("System.Title", ""),
            state=fields.get("System.State", ""),
            areaPath=fields.get("System.AreaPath", ""),
            assignedTo=assigned_to,
            analysisState=fields.get("Custom.ROBAnalysisState", ""),
            workItemType=fields.get("System.WorkItemType", ""),
            createdDate=fields.get("System.CreatedDate", ""),
            changedDate=fields.get("System.ChangedDate", ""),
            adoLink=ado.get_work_item_link(item["id"]),
        ))

    return TriageQueueDetailsResponse(
        items=items,
        count=len(items),
        totalAvailable=queue_result.get("total_available"),
        failedIds=batch_result.get("failed_ids", []),
    )


@app.get("/api/v1/ado/queue/saved", tags=["ADO"])
async def get_saved_query_results(
    query_id: str = Query(
        "b0ad9398-4942-4d8f-829e-604a347d8ac8",
        description="GUID of the saved ADO query",
    ),
    max_results: int = Query(500, ge=1, le=500),
):
    """
    Run a saved ADO query and return hydrated work items.

    Default query: "Azure Corp Daily Triage" — the standard triage queue.
    Returns all columns defined in the saved query plus key system fields.
    """
    try:
        ado = get_ado()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"ADO connection failed: {str(e)}"
        )

    result = ado.run_saved_query(query_id, max_results=max_results)

    if not result["success"]:
        raise HTTPException(
            status_code=502,
            detail=result.get("error", "Saved query failed"),
        )

    items = [
        SavedQueryItemSummary(
            id=item["id"],
            rev=item.get("rev", 0),
            fields=item.get("fields", {}),
            adoLink=item.get("adoLink", ""),
        )
        for item in result.get("items", [])
    ]

    raw_cols = result.get("columns", [])
    # Handle both old (List[str]) and new (List[dict]) column formats
    query_columns = [
        QueryColumn(**c) if isinstance(c, dict) else QueryColumn(referenceName=c, name=c.split(".")[-1])
        for c in raw_cols
    ]
    return SavedQueryResponse(
        queryName=result.get("queryName", ""),
        columns=query_columns,
        items=items,
        count=len(items),
        totalAvailable=result.get("totalAvailable"),
        failedIds=result.get("failedIds", []),
    )


@app.get("/api/v1/ado/workitem/{work_item_id}", tags=["ADO"])
async def get_work_item(work_item_id: int):
    """
    Fetch a single work item from ADO.
    
    Returns all fields for the specified work item, useful for
    inspection before or after evaluation.
    """
    try:
        ado = get_ado()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"ADO connection failed: {str(e)}"
        )
    
    result = ado.get_work_item(work_item_id)
    
    if not result["success"]:
        status = 404 if "not found" in result.get("error", "").lower() else 502
        raise HTTPException(status_code=status, detail=result["error"])
    
    return {
        "id": result["id"],
        "rev": result["rev"],
        "fields": result["fields"],
        "url": result.get("url"),
        "adoLink": ado.get_work_item_link(work_item_id),
    }


@app.get("/api/v1/ado/status", tags=["ADO"])
async def ado_connection_status():
    """
    Check ADO connection health.
    
    Verifies that the triage system can authenticate and
    reach the target ADO organization and project.
    """
    try:
        ado = get_ado()
        result = ado.test_connection()
        
        return AdoConnectionStatus(
            connected=result["success"],
            organization=result.get("organization"),
            project=result.get("project"),
            read_organization=result.get("read_organization"),
            read_project=result.get("read_project"),
            message=result.get("message"),
            error=result.get("error"),
        )
    except Exception as e:
        return AdoConnectionStatus(
            connected=False,
            error=str(e),
        )


@app.get("/api/v1/ado/fields", tags=["ADO"])
async def get_field_definitions():
    """
    Fetch field definitions from ADO for the Action work item type.
    
    Returns metadata about every field, including reference names,
    display names, data types, and allowed values.
    """
    try:
        ado = get_ado()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"ADO connection failed: {str(e)}"
        )
    
    result = ado.get_field_definitions()
    
    if not result["success"]:
        raise HTTPException(
            status_code=502,
            detail=result.get("error", "Failed to fetch field definitions")
        )
    
    return {
        "workItemType": result["work_item_type"],
        "fields": result["fields"],
        "count": len(result["fields"]),
    }


# =============================================================================
# Webhook Endpoint
# =============================================================================

@app.post("/api/v1/webhook/workitem", tags=["Webhook"])
async def receive_webhook(payload: WebhookPayload):
    """
    Receive ADO Service Hook webhook notifications.
    
    Called by ADO when a work item is created or updated.
    The processor determines whether to trigger evaluation.
    
    Setup:
        Configure an ADO Service Hook subscription pointing to:
        POST https://{host}:8009/api/v1/webhook/workitem
        
        Event types: workitem.created, workitem.updated
        Filters: Work Item Type = Action
    
    Returns 200 immediately (ADO expects fast webhook responses).
    Evaluation is triggered synchronously for now; future: background queue.
    """
    processor = get_webhook()
    
    result = processor.process(payload)
    
    if result["should_evaluate"]:
        # Trigger evaluation for this work item
        # The webhook payload might not have all fields, so we
        # re-fetch from ADO to get complete data
        try:
            ado = get_ado()
            eval_service = get_eval()
            
            ado_result = ado.get_work_item(result["work_item_id"])
            
            if ado_result["success"]:
                evaluation = eval_service.evaluate(
                    work_item_id=result["work_item_id"],
                    work_item_data=ado_result["fields"],
                    analysis=None,
                    actor="webhook",
                    dry_run=False,
                )
                
                logger.info(
                    "Webhook evaluation complete for item %d: state=%s",
                    result['work_item_id'], evaluation.analysisState,
                )
            else:
                logger.warning(
                    "Webhook failed to fetch item %d: %s",
                    result['work_item_id'], ado_result.get('error'),
                )
                
        except Exception as e:
            # Log but don't fail the webhook response
            # ADO will retry if we return non-200
            logger.error(
                "Webhook evaluation error for item %d: %s",
                result['work_item_id'], e, exc_info=True,
            )
    
    return WebhookResponse(
        received=True,
        workItemId=result["work_item_id"],
        shouldEvaluate=result["should_evaluate"],
        skipReason=result.get("skip_reason"),
    )


@app.get("/api/v1/webhook/stats", tags=["Webhook"])
async def webhook_stats():
    """Get webhook processing statistics"""
    processor = get_webhook()
    return processor.get_stats()


# =============================================================================
# Audit Endpoints
# =============================================================================

@app.get("/api/v1/audit", tags=["Audit"])
async def list_audit(
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    limit: int = Query(50, le=200)
):
    """List recent audit entries with optional filters.
    Returns empty results when Cosmos DB is unavailable (graceful degradation)."""
    try:
        audit = get_audit()
        entries = audit.get_recent(
            entity_type=entity_type,
            action=action,
            actor=actor,
            limit=limit
        )
        return {"entries": entries, "count": len(entries)}
    except Exception as e:
        # Graceful degradation: return empty audit list instead of 500
        logger.warning("Audit list unavailable (Cosmos offline): %s", e)
        return {"entries": [], "count": 0, "warning": f"Audit unavailable: {str(e)}"}


@app.get("/api/v1/audit/{entity_type}/{entity_id}", tags=["Audit"])
async def get_entity_audit(entity_type: str, entity_id: str, limit: int = 50):
    """Get audit history for a specific entity.
    Returns empty results when Cosmos DB is unavailable."""
    try:
        audit = get_audit()
        entries = audit.get_entity_history(entity_type, entity_id, limit)
        return {"entityType": entity_type, "entityId": entity_id, "entries": entries}
    except Exception as e:
        logger.warning("Entity audit unavailable (Cosmos offline): %s", e)
        return {"entityType": entity_type, "entityId": entity_id, "entries": [],
                "warning": f"Audit unavailable: {str(e)}"}


# =============================================================================
# Validation Endpoints
# =============================================================================

@app.get("/api/v1/validation/warnings", tags=["Validation"])
async def get_validation_warnings():
    """
    Get all validation warnings across the system.
    
    Checks for:
        - Orphaned rules (not referenced by any trigger)
        - Orphaned actions (not referenced by any route)
        - Missing references (triggers pointing to deleted rules/routes)
        - Duplicate priorities (triggers with the same priority)
    """
    crud = get_crud()
    warnings = []
    
    try:
        # Check for orphaned rules
        all_rules, _ = crud.list("rule")
        all_triggers, _ = crud.list("trigger")
        
        # Collect all rule IDs referenced by triggers
        referenced_rules = set()
        for trigger_doc in all_triggers:
            from ..models.trigger import Trigger
            trigger = Trigger.from_dict(trigger_doc)
            referenced_rules.update(trigger.get_referenced_rule_ids())
        
        for rule in all_rules:
            if rule["id"] not in referenced_rules:
                warnings.append({
                    "type": "orphaned_rule",
                    "entityType": "rule",
                    "entityId": rule["id"],
                    "message": f"Rule '{rule['name']}' is not used by any trigger",
                })
        
        # Check for orphaned actions
        all_actions, _ = crud.list("action")
        all_routes, _ = crud.list("route")
        
        referenced_actions = set()
        for route_doc in all_routes:
            for action_id in route_doc.get("actions", []):
                referenced_actions.add(action_id)
        
        for action in all_actions:
            if action["id"] not in referenced_actions:
                warnings.append({
                    "type": "orphaned_action",
                    "entityType": "action",
                    "entityId": action["id"],
                    "message": f"Action '{action['name']}' is not used by any route",
                })
        
        # Check for duplicate trigger priorities
        priorities = {}
        for trigger in all_triggers:
            p = trigger.get("priority")
            if p in priorities:
                warnings.append({
                    "type": "duplicate_priority",
                    "entityType": "trigger",
                    "entityId": trigger["id"],
                    "message": (
                        f"Trigger '{trigger['name']}' has the same priority ({p}) "
                        f"as trigger '{priorities[p]}'"
                    ),
                })
            else:
                priorities[p] = trigger.get("name", trigger["id"])
        
        # ==============================================================
        # Broken references: triggers → rules that don't exist
        # ==============================================================
        all_rule_ids = {r["id"] for r in all_rules}
        for trigger_doc in all_triggers:
            from ..models.trigger import Trigger as DT
            trigger = DT.from_dict(trigger_doc)
            for ref_rule_id in trigger.get_referenced_rule_ids():
                if ref_rule_id not in all_rule_ids:
                    warnings.append({
                        "type": "broken_reference",
                        "entityType": "trigger",
                        "entityId": trigger.id,
                        "message": (
                            f"Trigger '{trigger.name}' references rule "
                            f"'{ref_rule_id}' which does not exist"
                        ),
                    })
        
        # ==============================================================
        # Broken references: routes → actions that don't exist
        # ==============================================================
        all_action_ids = {a["id"] for a in all_actions}
        for route_doc in all_routes:
            for action_id in route_doc.get("actions", []):
                if action_id not in all_action_ids:
                    warnings.append({
                        "type": "broken_reference",
                        "entityType": "route",
                        "entityId": route_doc["id"],
                        "message": (
                            f"Route '{route_doc.get('name', route_doc['id'])}' "
                            f"references action '{action_id}' which does not exist"
                        ),
                    })
        
        # ==============================================================
        # Broken references: triggers → routes that don't exist
        # ==============================================================
        all_route_ids = {r["id"] for r in all_routes}
        for trigger_doc in all_triggers:
            on_true = trigger_doc.get("onTrue", "")
            if on_true and on_true not in all_route_ids:
                warnings.append({
                    "type": "broken_reference",
                    "entityType": "trigger",
                    "entityId": trigger_doc["id"],
                    "message": (
                        f"Trigger '{trigger_doc.get('name', trigger_doc['id'])}' "
                        f"points to route '{on_true}' which does not exist"
                    ),
                })
        
    except Exception as e:
        warnings.append({
            "type": "error",
            "entityType": "system",
            "entityId": "validation",
            "message": f"Error running validation: {str(e)}",
        })
    
    return {"warnings": warnings, "count": len(warnings)}


@app.get(
    "/api/v1/validation/references/{entity_type}/{entity_id}",
    tags=["Validation"]
)
async def get_references(entity_type: str, entity_id: str):
    """Get all entities that reference the given entity"""
    crud = get_crud()
    refs = crud.find_references(entity_type, entity_id)
    return {
        "entityType": entity_type,
        "entityId": entity_id,
        "references": refs,
    }


# =============================================================================
# Field Schema Endpoints
# =============================================================================

@app.get("/api/v1/fields", tags=["Fields"])
async def list_fields(
    source: Optional[str] = Query(None, description="Filter by source (ado, analysis, system)"),
    can_evaluate: Optional[bool] = Query(None, description="Filter to evaluable fields"),
    can_set: Optional[bool] = Query(None, description="Filter to settable fields"),
    group: Optional[str] = Query(None, description="Filter by display group"),
):
    """
    List available ADO field definitions.
    
    Used by the rule and action forms to provide field autocomplete.
    Returns field schemas with metadata about type, operators, and allowed values.
    
    Falls back to live ADO field definitions when the Cosmos field-schema
    container is empty or unavailable.
    """
    # ── Try Cosmos first ────────────────────────────────────────
    try:
        cosmos = get_cosmos_config()
        container = cosmos.get_container("field-schema")
        
        # Build query with optional filters
        # Note: "group" is a reserved SQL keyword — use c["group"] syntax
        conditions = []
        if source:
            conditions.append(f"c.source = '{source}'")
        if can_evaluate is not None:
            conditions.append(f"c.canEvaluate = {'true' if can_evaluate else 'false'}")
        if can_set is not None:
            conditions.append(f"c.canSet = {'true' if can_set else 'false'}")
        if group:
            conditions.append(f'c["group"] = \'{group}\'')
        
        where_clause = " AND ".join(conditions)
        query = f'SELECT * FROM c{" WHERE " + where_clause if where_clause else ""} ORDER BY c["group"], c.displayName'
        
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        
        if items:
            return {
                "items": items,
                "total": len(items),
            }
        # If Cosmos returned nothing, fall through to ADO
        logger.info("field-schema container is empty, falling back to live ADO fields")
    except Exception as e:
        logger.warning("Error querying field-schema container, falling back to ADO: %s", e)

    # ── Fallback: fetch live from ADO + Analysis fields ─────────
    try:
        ado = get_ado()
        result = ado.get_field_definitions()
        if not result.get("success"):
            raise HTTPException(
                status_code=502,
                detail=result.get("error", "Failed to fetch field definitions from ADO"),
            )

        # Map ADO field format → FieldCombobox expected format
        ado_fields = result.get("fields", [])
        items = []
        for f in ado_fields:
            ref = f.get("referenceName", "")
            # Derive a group from the reference name prefix (System, Custom, Microsoft, etc.)
            prefix = ref.split(".")[0] if "." in ref else "Other"
            items.append({
                "id": ref,
                "displayName": f.get("name", ref),
                "type": f.get("type", "string"),
                "description": f.get("helpText", ""),
                "source": "ado",
                "group": prefix,
                "canEvaluate": True,
                "canSet": not f.get("alwaysRequired", False),
            })

        # ── Add Analysis / Evaluation fields ──────────────────
        # These map to AnalysisResult.get_analysis_field() in the rules engine.
        # Prefixed with "Analysis." to match the rules engine resolution.
        analysis_fields = [
            {"id": "Analysis.Category",            "displayName": "Category",             "type": "string",  "description": "Primary category classification (e.g., feature_request, bug_report)"},
            {"id": "Analysis.Intent",              "displayName": "Intent",               "type": "string",  "description": "Inferred intent (e.g., requesting_feature, reporting_bug)"},
            {"id": "Analysis.Confidence",          "displayName": "Confidence",           "type": "double",  "description": "Overall analysis confidence score (0.0 – 1.0)"},
            {"id": "Analysis.Source",              "displayName": "Source",               "type": "string",  "description": "Analysis source method (hybrid, llm, pattern)"},
            {"id": "Analysis.Agreement",           "displayName": "Agreement",            "type": "boolean", "description": "Whether pattern engine and LLM classification agree"},
            {"id": "Analysis.BusinessImpact",      "displayName": "Business Impact",      "type": "string",  "description": "Business impact level (high / medium / low)"},
            {"id": "Analysis.TechnicalComplexity", "displayName": "Technical Complexity",  "type": "string",  "description": "Technical complexity level (high / medium / low)"},
            {"id": "Analysis.UrgencyLevel",        "displayName": "Urgency Level",        "type": "string",  "description": "Urgency level (high / medium / low)"},
            {"id": "Analysis.Products",            "displayName": "Detected Products",    "type": "list",    "description": "Azure products mentioned in the work item"},
            {"id": "Analysis.Services",            "displayName": "Azure & Modern Work Services", "type": "list", "description": "Azure and Modern Work service names detected (e.g., Route Server, Teams, SharePoint)"},
            {"id": "Analysis.Regions",             "displayName": "Regions / Locations",  "type": "list",    "description": "Geographic regions and Azure regions mentioned"},
            {"id": "Analysis.Technologies",        "displayName": "Technologies",         "type": "list",    "description": "Technologies referenced in the work item"},
            {"id": "Analysis.TechnicalAreas",      "displayName": "Technical Areas",      "type": "list",    "description": "Service categories (e.g., networking, security, ai_ml, modern_work)"},
            {"id": "Analysis.ComplianceFrameworks", "displayName": "Compliance Frameworks", "type": "list",   "description": "Compliance frameworks mentioned (NIST, ISO, HIPAA, etc.)"},
            {"id": "Analysis.DiscoveredServices",  "displayName": "Discovered Services",  "type": "list",    "description": "Services validated via Microsoft Learn API lookup"},
            {"id": "Analysis.KeyConcepts",         "displayName": "Key Concepts",         "type": "list",    "description": "Key concepts extracted from the work item"},
            {"id": "Analysis.SemanticKeywords",    "displayName": "Semantic Keywords",    "type": "list",    "description": "Keywords for search and matching"},
            {"id": "Analysis.ContextSummary",      "displayName": "Context Summary",      "type": "string",  "description": "Brief AI-generated summary of the work item"},
            {"id": "Analysis.Reasoning",           "displayName": "Reasoning",            "type": "string",  "description": "LLM reasoning for the classification decision"},
            {"id": "Analysis.PatternCategory",     "displayName": "Pattern Category",     "type": "string",  "description": "Category from the pattern matching engine"},
            {"id": "Analysis.PatternConfidence",   "displayName": "Pattern Confidence",   "type": "double",  "description": "Pattern engine confidence score (0.0 – 1.0)"},
        ]
        for af in analysis_fields:
            af["source"] = "analysis"
            af["group"] = "Analysis"
            af["canEvaluate"] = True
            af["canSet"] = False  # Analysis fields are read-only
        items.extend(analysis_fields)

        # Sort: Analysis group first, then ADO groups alphabetically
        def sort_key(x):
            g = x["group"]
            # Analysis fields sort before everything else
            return (0 if g == "Analysis" else 1, g, x["displayName"])
        items.sort(key=sort_key)

        return {
            "items": items,
            "total": len(items),
            "source": "ado-live",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching live ADO fields: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
