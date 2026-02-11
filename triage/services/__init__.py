"""
Triage Business Services
========================

Service layer providing business logic on top of models and engines:
    - CrudService: Create, read, update, delete for all entities
    - EvaluationService: Full pipeline orchestration
    - AuditService: Change tracking and logging
    - AdoClient: Azure DevOps REST API integration
    - AdoWriterService: Writes evaluation results to ADO
    - WebhookProcessor: Receives ADO Service Hook notifications
"""

from .crud_service import CrudService, ConflictError
from .audit_service import AuditService
from .evaluation_service import EvaluationService
from .ado_client import AdoClient, TriageAdoConfig, get_ado_client, reset_ado_client
from .ado_writer import AdoWriterService, AdoWriteResult, get_ado_writer, reset_ado_writer
from .webhook_receiver import WebhookProcessor, WebhookPayload

__all__ = [
    "CrudService",
    "ConflictError",
    "AuditService",
    "EvaluationService",
    "AdoClient",
    "TriageAdoConfig",
    "get_ado_client",
    "reset_ado_client",
    "AdoWriterService",
    "AdoWriteResult",
    "get_ado_writer",
    "reset_ado_writer",
    "WebhookProcessor",
    "WebhookPayload",
]
