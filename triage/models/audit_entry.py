"""
Audit Entry Model
=================

Represents a single audit log entry tracking changes to any triage entity.
Every create, update, delete, and status change generates an audit record.

Provides full traceability: who changed what, when, and what the before/after
values were. Stored in the audit-log container with entityType as partition key.

This is critical for:
    - Compliance (who approved a rule change?)
    - Debugging (when was this trigger disabled?)
    - Rollback investigation (what was the old value?)

Cosmos DB Container: audit-log
Partition Key: /entityType
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid

from .base import utc_now


# =============================================================================
# Audit Actions
# =============================================================================

class AuditAction:
    """
    Standard audit action names.
    
    Format: {entityType}.{operation}
    Examples: rule.create, trigger.update, route.delete
    """
    # CRUD operations
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    
    # Status changes
    ACTIVATE = "activate"
    DISABLE = "disable"
    STAGE = "stage"
    
    # Special operations
    COPY = "copy"
    IMPORT = "import"
    EXPORT = "export"
    
    # Evaluation
    EVALUATE = "evaluate"
    
    @classmethod
    def format_action(cls, entity_type: str, operation: str) -> str:
        """
        Format a full audit action string.
        
        Args:
            entity_type: Type of entity (rule, action, trigger, route)
            operation: Operation performed (create, update, delete, etc.)
            
        Returns:
            Formatted action string (e.g., "rule.update")
        """
        return f"{entity_type}.{operation}"


@dataclass
class AuditEntry:
    """
    A single audit log entry recording a change to a triage entity.
    
    Captures the complete context of the change:
        - Who: actor (user email)
        - What: entity type, entity ID, action performed
        - When: timestamp
        - Changes: before/after values for each modified field
        - Correlation: ID linking related operations
    
    Not a BaseEntity - audit entries are immutable append-only records.
    
    Attributes:
        id:             Unique audit ID (audit-{timestamp}-{uuid})
        timestamp:      When the change occurred
        action:         Qualified action (e.g., "rule.update")
        actor:          User email who made the change
        entityType:     Type of entity changed (partition key)
        entityId:       ID of the specific entity that changed
        changes:        Dict of field → {from, to} for each change
        correlationId:  Groups related audit entries together
        details:        Optional additional context or notes
    """
    
    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    id: str = ""                              # audit-{timestamp}-{short_uuid}
    timestamp: str = field(default_factory=utc_now)
    
    # -------------------------------------------------------------------------
    # What Changed
    # -------------------------------------------------------------------------
    action: str = ""                          # e.g., "rule.update"
    entityType: str = ""                      # rule | action | trigger | route
    entityId: str = ""                        # ID of the changed entity
    
    # -------------------------------------------------------------------------
    # Who Changed It
    # -------------------------------------------------------------------------
    actor: str = ""                           # User email or "system"
    
    # -------------------------------------------------------------------------
    # Change Details
    # -------------------------------------------------------------------------
    changes: Dict[str, Dict] = field(         # field → {from, to}
        default_factory=dict
    )
    
    # -------------------------------------------------------------------------
    # Correlation
    # -------------------------------------------------------------------------
    correlationId: str = ""                   # Groups related operations
    details: str = ""                         # Optional context notes
    
    def generate_id(self) -> str:
        """
        Generate a unique audit entry ID from timestamp and UUID.
        
        Format: audit-{YYYYMMDDHHmmss}-{short_uuid}
        
        Returns:
            Generated ID string
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        self.id = f"audit-{ts}-{short_uuid}"
        return self.id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Cosmos DB storage"""
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEntry':
        """Create from Cosmos DB document"""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    @classmethod
    def create(
        cls,
        action: str,
        entity_type: str,
        entity_id: str,
        actor: str,
        changes: Optional[Dict[str, Dict]] = None,
        correlation_id: str = "",
        details: str = ""
    ) -> 'AuditEntry':
        """
        Factory method to create a new audit entry with auto-generated ID.
        
        Args:
            action:         Operation performed (e.g., "create", "update")
            entity_type:    Type of entity (rule, action, trigger, route)
            entity_id:      ID of the changed entity
            actor:          User who made the change
            changes:        Field changes {field: {from, to}}
            correlation_id: Optional correlation ID
            details:        Optional context notes
            
        Returns:
            New AuditEntry with generated ID and formatted action
        """
        entry = cls(
            action=AuditAction.format_action(entity_type, action),
            entityType=entity_type,
            entityId=entity_id,
            actor=actor,
            changes=changes or {},
            correlationId=correlation_id or str(uuid.uuid4())[:8],
            details=details,
        )
        entry.generate_id()
        return entry
    
    def __repr__(self) -> str:
        change_count = len(self.changes)
        return (
            f"AuditEntry(action='{self.action}', "
            f"entity='{self.entityType}/{self.entityId}', "
            f"actor='{self.actor}', changes={change_count})"
        )
