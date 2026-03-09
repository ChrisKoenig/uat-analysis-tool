"""
Triage REST API
===============

FastAPI endpoints for the Triage Management System.
Runs on port 8009 alongside existing microservices.

API Groups:
    - /api/v1/rules              CRUD for atomic rules
    - /api/v1/actions            CRUD for atomic actions
    - /api/v1/triggers           CRUD for triggers
    - /api/v1/routes             CRUD for routes (action collections)
    - /api/v1/evaluate           Evaluation pipeline (full + dry run)
    - /api/v1/evaluate/apply     Apply evaluation results to ADO
    - /api/v1/ado/queue          Fetch triage queue from ADO
    - /api/v1/ado/workitem/{id}  Fetch single work item from ADO
    - /api/v1/ado/status         ADO connection health check
    - /api/v1/ado/fields         ADO field definitions
    - /api/v1/webhook/workitem   ADO Service Hook receiver
    - /api/v1/validation         Validation warnings and references
    - /api/v1/audit              Audit log access
    - /health                    Service health check
"""

from .routes import app
from .schemas import (
    RuleCreate, RuleUpdate,
    ActionCreate, ActionUpdate,
    TriggerCreate, TriggerUpdate,
    RouteCreate, RouteUpdate,
    EvaluateRequest, EvaluateResponse,
    StatusUpdate, CopyRequest,
    HealthResponse, ErrorResponse, ReferenceResponse,
    TriageQueueRequest, TriageQueueResponse,
    ApplyChangesRequest, ApplyChangesResponse,
    WebhookResponse, AdoConnectionStatus,
)

__all__ = [
    "app",
    "RuleCreate", "RuleUpdate",
    "ActionCreate", "ActionUpdate",
    "TriggerCreate", "TriggerUpdate",
    "RouteCreate", "RouteUpdate",
    "EvaluateRequest", "EvaluateResponse",
    "StatusUpdate", "CopyRequest",
    "HealthResponse", "ErrorResponse", "ReferenceResponse",
    "TriageQueueRequest", "TriageQueueResponse",
    "ApplyChangesRequest", "ApplyChangesResponse",
    "WebhookResponse", "AdoConnectionStatus",
]
