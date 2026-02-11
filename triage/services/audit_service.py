"""
Audit Service
=============

Centralized audit logging for the triage management system.
Every create, update, delete, status change, and evaluation is
recorded in the audit-log Cosmos DB container.

The audit service provides:
    - Structured logging of all entity changes
    - Query capabilities for audit history
    - Correlation tracking (group related changes)
    - Actor tracking (who made each change)

Audit entries are immutable - once written, they cannot be modified
or deleted (append-only log).

Cosmos DB Container: audit-log
Partition Key: /entityType
"""

from typing import Dict, List, Optional, Any
import logging

from ..config.cosmos_config import get_cosmos_config
from ..models.audit_entry import AuditEntry, AuditAction

logger = logging.getLogger("triage.services.audit")


class AuditService:
    """
    Manages audit log entries for all triage entity changes.
    
    Usage:
        service = AuditService()
        
        # Log a change
        service.log_change(
            action="update",
            entity_type="rule",
            entity_id="rule-1",
            actor="brad.price@microsoft.com",
            changes={"status": {"from": "active", "to": "disabled"}}
        )
        
        # Query audit history
        history = service.get_entity_history("rule", "rule-1")
        recent = service.get_recent(entity_type="rule", limit=50)
    """
    
    def __init__(self):
        """Initialize with Cosmos DB connection"""
        self._cosmos = get_cosmos_config()
    
    def log_change(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        actor: str,
        changes: Optional[Dict[str, Dict]] = None,
        correlation_id: str = "",
        details: str = ""
    ) -> AuditEntry:
        """
        Create and store an audit log entry.
        
        Args:
            action:         Operation (create, update, delete, etc.)
            entity_type:    Entity type (rule, action, trigger, route)
            entity_id:      ID of the affected entity
            actor:          User email or "system"
            changes:        Field changes {field: {from, to}}
            correlation_id: Groups related operations
            details:        Optional context notes
            
        Returns:
            The created AuditEntry
        """
        entry = AuditEntry.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            changes=changes,
            correlation_id=correlation_id,
            details=details,
        )
        
        try:
            container = self._cosmos.get_container("audit-log")
            container.create_item(body=entry.to_dict())
        except Exception as e:
            # Audit writes should not fail silently in production,
            # but also should not block the primary operation
            logger.error("ERROR writing audit entry: %s", e, exc_info=True)
        
        return entry
    
    def log_evaluation(
        self,
        work_item_id: int,
        actor: str,
        matched_trigger: Optional[str],
        applied_route: Optional[str],
        analysis_state: str,
        is_dry_run: bool = False
    ) -> AuditEntry:
        """
        Log an evaluation event.
        
        Args:
            work_item_id:    ADO work item ID
            actor:           Who triggered the evaluation
            matched_trigger: Trigger that matched (or None)
            applied_route:   Route that was applied (or None)
            analysis_state:  Resulting analysis state
            is_dry_run:      Whether this was a test run
            
        Returns:
            The created AuditEntry
        """
        return self.log_change(
            action=AuditAction.EVALUATE,
            entity_type="evaluation",
            entity_id=str(work_item_id),
            actor=actor,
            changes={
                "matchedTrigger": {"from": None, "to": matched_trigger},
                "appliedRoute": {"from": None, "to": applied_route},
                "analysisState": {"from": None, "to": analysis_state},
            },
            details=f"{'DRY RUN: ' if is_dry_run else ''}Evaluated work item {work_item_id}",
        )
    
    def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get the audit history for a specific entity.
        
        Returns audit entries in reverse chronological order.
        Uses the entityType partition key for efficient queries.
        
        Args:
            entity_type: Type of entity (rule, action, trigger, route)
            entity_id:   ID of the entity
            limit:       Maximum entries to return
            
        Returns:
            List of audit entry dicts, newest first
        """
        container = self._cosmos.get_container("audit-log")
        
        query = (
            "SELECT * FROM c "
            "WHERE c.entityType = @entityType "
            "AND c.entityId = @entityId "
            "ORDER BY c.timestamp DESC"
        )
        params = [
            {"name": "@entityType", "value": entity_type},
            {"name": "@entityId", "value": entity_id},
        ]
        
        items = list(container.query_items(
            query=query,
            parameters=params,
            partition_key=entity_type,
            max_item_count=limit
        ))
        
        return items
    
    def get_recent(
        self,
        entity_type: Optional[str] = None,
        actor: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent audit entries with optional filters.
        
        Args:
            entity_type: Filter by entity type
            actor:       Filter by actor email
            limit:       Maximum entries to return
            
        Returns:
            List of audit entry dicts, newest first
        """
        container = self._cosmos.get_container("audit-log")
        
        # Build query dynamically based on filters
        conditions = []
        params = []
        
        if entity_type:
            conditions.append("c.entityType = @entityType")
            params.append({"name": "@entityType", "value": entity_type})
        
        if actor:
            conditions.append("c.actor = @actor")
            params.append({"name": "@actor", "value": actor})
        
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        query = f"SELECT * FROM c{where} ORDER BY c.timestamp DESC"
        
        items = list(container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True,
            max_item_count=limit
        ))
        
        return items
    
    def get_correlation(self, correlation_id: str) -> List[Dict[str, Any]]:
        """
        Get all audit entries for a correlation ID.
        
        Useful for viewing all changes made as part of a single
        user action (e.g., bulk update that touches multiple entities).
        
        Args:
            correlation_id: The correlation ID to search for
            
        Returns:
            List of related audit entries
        """
        container = self._cosmos.get_container("audit-log")
        
        query = (
            "SELECT * FROM c "
            "WHERE c.correlationId = @correlationId "
            "ORDER BY c.timestamp ASC"
        )
        params = [
            {"name": "@correlationId", "value": correlation_id},
        ]
        
        items = list(container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True
        ))
        
        return items
