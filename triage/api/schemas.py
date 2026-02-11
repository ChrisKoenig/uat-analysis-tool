"""
API Schemas (Pydantic)
======================

Pydantic models for API request/response validation.
These define the JSON shapes that the REST API accepts and returns,
separate from the internal dataclass models.

Using Pydantic for API layer because:
    - Automatic JSON Schema generation for OpenAPI docs
    - Request validation with clear error messages
    - Response serialization
    - Type coercion
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Rule Schemas
# =============================================================================

class RuleCreate(BaseModel):
    """Request body for creating a rule"""
    name: str = Field(..., description="Human-readable rule name")
    description: str = Field("", description="Purpose of this rule")
    field: str = Field(..., description="ADO field reference (e.g., Custom.SolutionArea)")
    operator: str = Field(..., description="Comparison operator (e.g., equals, in, isNull)")
    value: Any = Field(None, description="Comparison value (type depends on operator)")
    status: str = Field("active", description="active | disabled | staged")


class RuleUpdate(BaseModel):
    """Request body for updating a rule"""
    name: Optional[str] = None
    description: Optional[str] = None
    field: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    status: Optional[str] = None
    version: int = Field(..., description="Current version for optimistic locking")


# =============================================================================
# Action Schemas
# =============================================================================

class ActionCreate(BaseModel):
    """Request body for creating an action"""
    name: str = Field(..., description="Human-readable action name")
    description: str = Field("", description="Purpose of this action")
    field: str = Field(..., description="ADO field to modify")
    operation: str = Field(..., description="Operation: set, set_computed, copy, append, template")
    value: Any = Field(None, description="Value to apply (depends on operation)")
    valueType: str = Field("static", description="Value type hint: static, computed, field_ref, template")
    status: str = Field("active", description="active | disabled | staged")


class ActionUpdate(BaseModel):
    """Request body for updating an action"""
    name: Optional[str] = None
    description: Optional[str] = None
    field: Optional[str] = None
    operation: Optional[str] = None
    value: Any = None
    valueType: Optional[str] = None
    status: Optional[str] = None
    version: int = Field(..., description="Current version for optimistic locking")


# =============================================================================
# Trigger Schemas
# =============================================================================

class TriggerCreate(BaseModel):
    """Request body for creating a trigger"""
    name: str = Field(..., description="Human-readable trigger name")
    description: str = Field("", description="Purpose of this trigger")
    priority: int = Field(..., description="Evaluation order (lower = higher priority)")
    expression: Dict = Field(..., description="Nested AND/OR expression referencing rule IDs")
    onTrue: str = Field(..., description="Route ID to execute when True")
    status: str = Field("active", description="active | disabled | staged")


class TriggerUpdate(BaseModel):
    """Request body for updating a trigger"""
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    expression: Optional[Dict] = None
    onTrue: Optional[str] = None
    status: Optional[str] = None
    version: int = Field(..., description="Current version for optimistic locking")


# =============================================================================
# Route Schemas
# =============================================================================

class RouteCreate(BaseModel):
    """Request body for creating a route"""
    name: str = Field(..., description="Human-readable route name")
    description: str = Field("", description="Purpose of this route")
    actions: List[str] = Field(..., description="Ordered list of action IDs")
    status: str = Field("active", description="active | disabled | staged")


class RouteUpdate(BaseModel):
    """Request body for updating a route"""
    name: Optional[str] = None
    description: Optional[str] = None
    actions: Optional[List[str]] = None
    status: Optional[str] = None
    version: int = Field(..., description="Current version for optimistic locking")


# =============================================================================
# Evaluation Schemas
# =============================================================================

class EvaluateRequest(BaseModel):
    """Request body for triggering an evaluation"""
    workItemIds: List[int] = Field(
        ..., description="List of ADO work item IDs to evaluate"
    )
    dryRun: bool = Field(
        False, description="If True, compute results without writing to ADO"
    )


class EvaluateResponse(BaseModel):
    """Response for an evaluation"""
    id: str
    workItemId: int
    analysisState: str
    matchedTrigger: Optional[str] = None
    appliedRoute: Optional[str] = None
    actionsExecuted: List[str] = []
    ruleResults: Dict[str, bool] = {}
    fieldsChanged: Dict[str, Dict] = {}
    errors: List[str] = []
    isDryRun: bool = False


# =============================================================================
# Queue Schemas
# =============================================================================

class TriageQueueRequest(BaseModel):
    """Request body for fetching the triage queue from ADO"""
    stateFilter: Optional[str] = Field(
        None,
        description="Filter by ROBAnalysisState (e.g., 'Pending', 'Awaiting Approval')"
    )
    areaPath: Optional[str] = Field(
        None, description="Filter by area path (hierarchical)"
    )
    maxResults: int = Field(
        100, description="Maximum items to return", ge=1, le=500
    )


class TriageQueueResponse(BaseModel):
    """Response for the triage queue"""
    workItemIds: List[int] = []
    count: int = 0
    totalAvailable: Optional[int] = None


class QueueItemSummary(BaseModel):
    """Hydrated queue item with key fields for display"""
    id: int
    rev: int
    title: str = ""
    state: str = ""
    areaPath: str = ""
    assignedTo: str = ""
    analysisState: str = ""
    workItemType: str = ""
    createdDate: str = ""
    changedDate: str = ""
    adoLink: str = ""


class TriageQueueDetailsResponse(BaseModel):
    """Hydrated triage queue with full item summaries"""
    items: List[QueueItemSummary] = []
    count: int = 0
    totalAvailable: Optional[int] = None
    failedIds: List[int] = []


class SavedQueryItemSummary(BaseModel):
    """Work item from a saved ADO query with all field data."""
    id: int
    rev: int = 0
    fields: Dict[str, Any] = {}
    adoLink: str = ""


class SavedQueryResponse(BaseModel):
    """Response from running a saved ADO query."""
    queryName: str = ""
    columns: List[str] = []
    items: List[SavedQueryItemSummary] = []
    count: int = 0
    totalAvailable: Optional[int] = None
    failedIds: List[int] = []


class AnalyzeRequest(BaseModel):
    """Request body for running analysis on work items."""
    workItemIds: List[int] = Field(
        ..., description="ADO work item IDs to analyze"
    )


class AnalysisStateRequest(BaseModel):
    """Request body for updating ROBAnalysisState on ADO work items."""
    workItemIds: List[int] = Field(
        ..., description="ADO work item IDs to update"
    )
    state: str = Field(
        ..., description="New ROBAnalysisState value (e.g., 'Awaiting Approval', 'Pending')"
    )


class ApplyChangesRequest(BaseModel):
    """Request body for applying evaluation results to ADO"""
    evaluationId: str = Field(
        ..., description="Evaluation ID whose changes to apply"
    )
    workItemId: int = Field(
        ..., description="ADO work item ID to update"
    )
    revision: Optional[int] = Field(
        None, description="Expected revision for conflict detection"
    )


class ApplyChangesResponse(BaseModel):
    """Response for applying changes"""
    success: bool
    workItemId: int
    fieldsUpdated: int = 0
    commentPosted: bool = False
    newRevision: Optional[int] = None
    error: Optional[str] = None
    conflict: bool = False


class WebhookResponse(BaseModel):
    """Response returned to ADO Service Hook after receiving a webhook"""
    received: bool = True
    workItemId: Optional[int] = None
    shouldEvaluate: bool = False
    skipReason: Optional[str] = None


class AdoConnectionStatus(BaseModel):
    """ADO connection health check response"""
    connected: bool
    organization: Optional[str] = None
    project: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Common Schemas
# =============================================================================

class StatusUpdate(BaseModel):
    """Request body for changing entity status"""
    status: str = Field(..., description="New status: active | disabled | staged")
    version: int = Field(
        ..., description="Current version for optimistic locking"
    )


class CopyRequest(BaseModel):
    """Request body for copying/cloning an entity"""
    newName: Optional[str] = Field(
        None, description="Name for the copy (default: 'Copy of {name}')"
    )


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    database: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None


class ReferenceResponse(BaseModel):
    """Cross-reference response"""
    entityType: str
    entityId: str
    references: Dict[str, List[str]]
