"""
Triage API - FastAPI Application
=================================

Main FastAPI application for the Triage Management System.
Runs on port 8009 alongside the existing microservices.

Endpoints:
    /api/v1/rules      - CRUD for rules
    /api/v1/actions     - CRUD for actions
    /api/v1/trees       - CRUD for decision trees
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
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("triage.api")

from .schemas import (
    RuleCreate, RuleUpdate,
    ActionCreate, ActionUpdate,
    TreeCreate, TreeUpdate,
    RouteCreate, RouteUpdate,
    EvaluateRequest, EvaluateResponse,
    StatusUpdate, CopyRequest,
    HealthResponse, ErrorResponse, ReferenceResponse,
    TriageQueueRequest, TriageQueueResponse,
    TriageQueueDetailsResponse, QueueItemSummary,
    ApplyChangesRequest, ApplyChangesResponse,
    WebhookResponse, AdoConnectionStatus,
)
from ..services.crud_service import CrudService, ConflictError
from ..services.evaluation_service import EvaluationService
from ..services.audit_service import AuditService
from ..services.ado_client import AdoClient, get_ado_client, TriageAdoConfig
from ..services.webhook_receiver import WebhookProcessor, WebhookPayload
from ..config.cosmos_config import get_cosmos_config


# =============================================================================
# Application Setup
# =============================================================================

app = FastAPI(
    title="Triage Management API",
    description=(
        "REST API for the Triage Management System. "
        "Manages rules, actions, decision trees, and routes for "
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
# Since rules, actions, trees, and routes all follow the same CRUD pattern,
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
    plural = f"{entity_type}s" if entity_type != "tree" else "trees"
    tag = entity_type.capitalize() + "s"
    
    # --- LIST ---
    @app.get(f"/api/v1/{plural}", tags=[tag])
    async def list_entities(
        status: Optional[str] = Query(None, description="Filter by status")
    ):
        """List entities with optional status filter.
        Returns empty results when Cosmos DB is unavailable (graceful degradation)."""
        try:
            crud = get_crud()
            items, token = crud.list(entity_type, status=status)
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
        Returns empty refs when Cosmos DB is unavailable."""
        try:
            crud = get_crud()
            refs = crud.find_references(entity_type, entity_id)
            return ReferenceResponse(
                entityType=entity_type,
                entityId=entity_id,
                references=refs
            )
        except Exception as e:
            logger.warning("References unavailable (Cosmos offline): %s", e)
            return {"entityType": entity_type, "entityId": entity_id,
                    "references": [], "warning": str(e)}
    
    get_references.__name__ = f"get_{entity_type}_references"
    get_references.__qualname__ = f"get_{entity_type}_references"


# =============================================================================
# Register CRUD Endpoints for All Entity Types
# =============================================================================

_create_crud_endpoints("rule", RuleCreate, RuleUpdate)
_create_crud_endpoints("action", ActionCreate, ActionUpdate)
_create_crud_endpoints("tree", TreeCreate, TreeUpdate)
_create_crud_endpoints("route", RouteCreate, RouteUpdate)


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
        3. Walk decision trees → find first matching tree
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
    
    # Run evaluation pipeline for each item
    for item in items_data:
        work_item_id = item["id"]
        fields = item["fields"]
        
        # TODO: In a future phase, also fetch/load AnalysisResult from Cosmos
        # For now, analysis data would come from the existing analysis engine
        
        evaluation = eval_service.evaluate(
            work_item_id=work_item_id,
            work_item_data=fields,
            analysis=None,  # Phase 2: analysis integration pending
            actor="api-user",
            dry_run=body.dryRun,
        )
        
        results.append({
            "id": evaluation.id,
            "workItemId": work_item_id,
            "analysisState": evaluation.analysisState,
            "matchedTree": evaluation.matchedTree,
            "appliedRoute": evaluation.appliedRoute,
            "actionsExecuted": evaluation.actionsExecuted,
            "ruleResults": evaluation.ruleResults,
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
    actor: Optional[str] = Query(None),
    limit: int = Query(50, le=200)
):
    """List recent audit entries with optional filters.
    Returns empty results when Cosmos DB is unavailable (graceful degradation)."""
    try:
        audit = get_audit()
        entries = audit.get_recent(
            entity_type=entity_type,
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
        - Orphaned rules (not referenced by any tree)
        - Orphaned actions (not referenced by any route)
        - Missing references (trees pointing to deleted rules/routes)
        - Duplicate priorities (trees with the same priority)
    """
    crud = get_crud()
    warnings = []
    
    try:
        # Check for orphaned rules
        all_rules, _ = crud.list("rule")
        all_trees, _ = crud.list("tree")
        
        # Collect all rule IDs referenced by trees
        referenced_rules = set()
        for tree_doc in all_trees:
            from ..models.tree import DecisionTree
            tree = DecisionTree.from_dict(tree_doc)
            referenced_rules.update(tree.get_referenced_rule_ids())
        
        for rule in all_rules:
            if rule["id"] not in referenced_rules:
                warnings.append({
                    "type": "orphaned_rule",
                    "entityType": "rule",
                    "entityId": rule["id"],
                    "message": f"Rule '{rule['name']}' is not used by any tree",
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
        
        # Check for duplicate tree priorities
        priorities = {}
        for tree in all_trees:
            p = tree.get("priority")
            if p in priorities:
                warnings.append({
                    "type": "duplicate_priority",
                    "entityType": "tree",
                    "entityId": tree["id"],
                    "message": (
                        f"Tree '{tree['name']}' has the same priority ({p}) "
                        f"as tree '{priorities[p]}'"
                    ),
                })
            else:
                priorities[p] = tree.get("name", tree["id"])
        
        # ==============================================================
        # Broken references: trees → rules that don't exist
        # ==============================================================
        all_rule_ids = {r["id"] for r in all_rules}
        for tree_doc in all_trees:
            from ..models.tree import DecisionTree as DT
            tree = DT.from_dict(tree_doc)
            for ref_rule_id in tree.get_referenced_rule_ids():
                if ref_rule_id not in all_rule_ids:
                    warnings.append({
                        "type": "broken_reference",
                        "entityType": "tree",
                        "entityId": tree.id,
                        "message": (
                            f"Tree '{tree.name}' references rule "
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
        # Broken references: trees → routes that don't exist
        # ==============================================================
        all_route_ids = {r["id"] for r in all_routes}
        for tree_doc in all_trees:
            on_true = tree_doc.get("onTrue", "")
            if on_true and on_true not in all_route_ids:
                warnings.append({
                    "type": "broken_reference",
                    "entityType": "tree",
                    "entityId": tree_doc["id"],
                    "message": (
                        f"Tree '{tree_doc.get('name', tree_doc['id'])}' "
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
