"""
Base Model
==========

Provides the base dataclass and shared fields for all triage entities.
All domain models (Rule, Action, Trigger, Route) inherit these common
audit and lifecycle fields.

Fields:
    id:           Unique identifier (e.g., "rule-1", "dt-10")
    name:         Human-readable display name
    description:  Longer explanation of purpose
    status:       Lifecycle state: active | disabled | staged
    version:      Optimistic locking counter (incremented on each update)
    createdBy:    Email of the user who created the entity
    createdDate:  ISO 8601 timestamp of creation
    modifiedBy:   Email of the last user to modify the entity
    modifiedDate: ISO 8601 timestamp of last modification
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any


class EntityStatus(str, Enum):
    """
    Lifecycle status for all triage entities.
    
    - active:   Live in production, used during evaluation
    - disabled: Turned off, not evaluated (but preserved for history)
    - staged:   Test-only, visible in test mode but not live evaluations
    """
    ACTIVE = "active"
    DISABLED = "disabled"
    STAGED = "staged"


def utc_now() -> str:
    """Get current UTC timestamp in ISO 8601 format"""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BaseEntity:
    """
    Base class for all triage domain entities.
    
    Provides common fields for identification, lifecycle management,
    versioning (optimistic locking), and audit tracking.
    
    All entities stored in Cosmos DB include these fields.
    The `status` field serves as the partition key for rules, actions,
    triggers, and routes containers.
    """
    
    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    id: str = ""                    # Unique identifier (e.g., "rule-1")
    name: str = ""                  # Human-readable display name
    description: str = ""           # Purpose/explanation
    
    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------
    status: str = EntityStatus.ACTIVE  # active | disabled | staged
    version: int = 1                   # Optimistic locking version counter
    
    # -------------------------------------------------------------------------
    # Audit
    # -------------------------------------------------------------------------
    createdBy: str = ""                # Email of creator
    createdDate: str = field(default_factory=utc_now)  # ISO 8601 creation time
    modifiedBy: str = ""               # Email of last modifier
    modifiedDate: str = field(default_factory=utc_now) # ISO 8601 last modified
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert entity to a dictionary suitable for Cosmos DB storage.
        
        Uses dataclass asdict() for automatic field serialization.
        Subclasses can override to customize serialization.
        
        Returns:
            Dict with all entity fields
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEntity':
        """
        Create an entity instance from a Cosmos DB document.
        
        Filters out unknown fields to handle forward compatibility
        (documents may contain fields added in newer versions).
        
        Args:
            data: Dict from Cosmos DB (may include _rid, _self, etc.)
            
        Returns:
            New entity instance
        """
        # Filter to only known fields for this dataclass
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    def bump_version(self, modified_by: str) -> None:
        """
        Increment version and update audit fields for a modification.
        
        Called before saving an updated entity to Cosmos DB.
        The version field enables optimistic concurrency control:
        updates include the expected version, and Cosmos DB rejects
        stale writes.
        
        Args:
            modified_by: Email of the user making the change
        """
        self.version += 1
        self.modifiedBy = modified_by
        self.modifiedDate = utc_now()
    
    def validate(self) -> list:
        """
        Validate required fields. Returns list of error messages.
        
        Subclasses should call super().validate() and extend the list
        with their own validation rules.
        
        Returns:
            List of validation error strings (empty = valid)
        """
        errors = []
        
        if not self.id:
            errors.append("id is required")
        if not self.name:
            errors.append("name is required")
        if self.status not in [s.value for s in EntityStatus]:
            errors.append(
                f"status must be one of: {[s.value for s in EntityStatus]}"
            )
        if self.version < 1:
            errors.append("version must be >= 1")
            
        return errors
