"""
Triage Data Models
==================

Defines the core data structures for the four-layer triage model:
    - Rule: Atomic condition (field + operator + value) → True/False
    - Action: Atomic field assignment (field + operation + value)
    - DecisionTree: Chains rules with AND/OR logic, maps to a route
    - Route: Collection of actions to execute
    - Evaluation: Per-item rule evaluation results
    - AnalysisResult: Structured analysis output
    - FieldSchema: ADO field definitions and metadata
    - AuditEntry: Change tracking records

All managed models include:
    - Status management (active/disabled/staged)
    - Version tracking for optimistic locking
    - Audit fields (createdBy, modifiedBy, timestamps)
"""

from .base import BaseEntity, EntityStatus, utc_now
from .rule import Rule, VALID_OPERATORS
from .action import Action, VALID_OPERATIONS, TEMPLATE_VARIABLES
from .tree import DecisionTree
from .route import Route
from .evaluation import Evaluation, AnalysisState
from .analysis_result import AnalysisResult
from .field_schema import FieldSchema
from .audit_entry import AuditEntry, AuditAction

__all__ = [
    # Base
    "BaseEntity",
    "EntityStatus",
    "utc_now",
    # Core entities
    "Rule",
    "Action",
    "DecisionTree",
    "Route",
    # Results
    "Evaluation",
    "AnalysisState",
    "AnalysisResult",
    # Schema & Audit
    "FieldSchema",
    "AuditEntry",
    "AuditAction",
    # Constants
    "VALID_OPERATORS",
    "VALID_OPERATIONS",
    "TEMPLATE_VARIABLES",
]
