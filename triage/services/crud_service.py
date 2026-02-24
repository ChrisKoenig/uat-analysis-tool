"""
CRUD Service
=============

Generic CRUD (Create, Read, Update, Delete) operations for all triage entities.
Handles Cosmos DB interactions with optimistic locking, status management,
partition key routing, and audit trail generation.

Each entity type (rules, actions, triggers, routes) uses the same CRUD patterns
with entity-specific validation. This service provides the shared implementation
that the API endpoints delegate to.

Features:
    - Create with auto-generated ID and audit fields
    - Read with partition key optimization
    - Update with optimistic locking (version check)
    - Delete (soft via status change or hard delete)
    - List with status filtering and pagination
    - Copy/clone entities
    - Cross-reference validation (who uses this entity?)

All mutations generate audit log entries via the AuditService.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple, Type

from ..config.cosmos_config import get_cosmos_config
from ..models.base import BaseEntity, EntityStatus, utc_now
from ..models.rule import Rule
from ..models.action import Action
from ..models.trigger import Trigger
from ..models.route import Route
from ..models.triage_team import TriageTeam
from ..models.audit_entry import AuditEntry, AuditAction

logger = logging.getLogger("triage.services.crud")


# =============================================================================
# Entity Registry
# =============================================================================
# Maps entity type names to their model classes and container names.
# Used for generic CRUD operations shared across all entity types.

ENTITY_REGISTRY = {
    "rule": {
        "model_class": Rule,
        "container": "rules",
        "id_prefix": "rule",
    },
    "action": {
        "model_class": Action,
        "container": "actions",
        "id_prefix": "action",
    },
    "trigger": {
        "model_class": Trigger,
        "container": "triggers",
        "id_prefix": "dt",
    },
    "route": {
        "model_class": Route,
        "container": "routes",
        "id_prefix": "route",
    },
    "triage-team": {
        "model_class": TriageTeam,
        "container": "triage-teams",
        "id_prefix": "team",
    },
}


class CrudService:
    """
    Generic CRUD service for triage entities (rules, actions, triggers, routes).
    
    Handles all Cosmos DB interactions with proper partition key routing,
    optimistic locking, and audit trail generation.
    
    Usage:
        service = CrudService()
        
        # Create a new rule
        rule = service.create("rule", {
            "name": "Milestone ID is Null",
            "field": "Custom.MilestoneID",
            "operator": "isNull"
        }, actor="brad.price@microsoft.com")
        
        # List all active rules
        rules = service.list("rule", status="active")
        
        # Update a rule
        updated = service.update("rule", "rule-1", {
            "value": "new-value",
            "version": 1  # optimistic lock
        }, actor="brad.price@microsoft.com")
    """
    
    def __init__(self):
        """Initialize with Cosmos DB connection"""
        self._cosmos = get_cosmos_config()
        self._audit_entries: List[AuditEntry] = []  # Pending audit writes
    
    # =========================================================================
    # CREATE
    # =========================================================================
    
    def create(
        self,
        entity_type: str,
        data: Dict[str, Any],
        actor: str = "system"
    ) -> Dict[str, Any]:
        """
        Create a new entity.
        
        Auto-generates ID if not provided. Sets version=1, status=active,
        and populates audit fields (createdBy, createdDate, etc.).
        
        Args:
            entity_type: Type of entity (rule, action, trigger, route)
            data:        Entity data dict
            actor:       Email of the creating user
            
        Returns:
            Created entity as dict (includes generated ID)
            
        Raises:
            ValueError: If entity_type is unknown or validation fails
        """
        registry = self._get_registry(entity_type)
        model_class = registry["model_class"]
        container_name = registry["container"]
        
        # Auto-generate ID if not provided
        if "id" not in data or not data["id"]:
            data["id"] = self._generate_id(registry["id_prefix"])
        
        # Set default values for new entity
        now = utc_now()
        data.setdefault("status", EntityStatus.ACTIVE)
        data.setdefault("version", 1)
        data["createdBy"] = actor
        data["createdDate"] = now
        data["modifiedBy"] = actor
        data["modifiedDate"] = now
        
        # Create model instance for validation
        entity = model_class.from_dict(data)
        errors = entity.validate()
        if errors:
            raise ValueError(
                f"Validation failed for {entity_type}: {errors}"
            )
        
        # Write to Cosmos DB
        container = self._cosmos.get_container(container_name)
        doc = entity.to_dict()
        result = container.create_item(body=doc)
        
        # Generate audit entry
        self._create_audit_entry(
            action=AuditAction.CREATE,
            entity_type=entity_type,
            entity_id=entity.id,
            actor=actor,
            changes={"_created": {"from": None, "to": entity.id}},
        )
        
        logger.info("Created %s '%s': %s", entity_type, entity.id, entity.name)
        return result
    
    # =========================================================================
    # READ
    # =========================================================================
    
    def get(
        self,
        entity_type: str,
        entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single entity by ID.
        
        Queries across all partition key values (status) since we don't
        know the entity's status from just its ID.
        
        Args:
            entity_type: Type of entity (rule, action, trigger, route)
            entity_id:   The entity's ID
            
        Returns:
            Entity as dict, or None if not found
        """
        registry = self._get_registry(entity_type)
        container = self._cosmos.get_container(registry["container"])
        
        # Query by ID across all partitions
        query = "SELECT * FROM c WHERE c.id = @id"
        params = [{"name": "@id", "value": entity_id}]
        
        items = list(container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True
        ))
        
        found = items[0] if items else None
        logger.debug("get %s '%s' → %s", entity_type, entity_id, "found" if found else "NOT FOUND")
        return found
    
    def list(
        self,
        entity_type: str,
        status: Optional[str] = None,
        page_size: int = 100,
        continuation_token: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        List entities with optional status filter.
        
        When status is provided, the query is partition-scoped (efficient).
        Without status, queries across all partitions.
        
        Args:
            entity_type:         Entity type to list
            status:              Filter by status (active/disabled/staged)
            page_size:           Max items per page
            continuation_token:  Token for next page
            
        Returns:
            Tuple of (items list, next continuation token or None)
        """
        registry = self._get_registry(entity_type)
        container = self._cosmos.get_container(registry["container"])
        
        if status:
            # Partition-scoped query (efficient)
            query = "SELECT * FROM c WHERE c.status = @status"
            params = [{"name": "@status", "value": status}]
            items = list(container.query_items(
                query=query,
                parameters=params,
                partition_key=status,
                max_item_count=page_size
            ))
        else:
            # Cross-partition query (all statuses)
            query = "SELECT * FROM c ORDER BY c.modifiedDate DESC"
            items = list(container.query_items(
                query=query,
                enable_cross_partition_query=True,
                max_item_count=page_size
            ))
        
        # TODO: Implement proper continuation token support
        return items, None
    
    # =========================================================================
    # UPDATE
    # =========================================================================
    
    def update(
        self,
        entity_type: str,
        entity_id: str,
        data: Dict[str, Any],
        actor: str = "system"
    ) -> Dict[str, Any]:
        """
        Update an existing entity with optimistic locking.
        
        The caller must provide the current version number in data["version"].
        If the stored version doesn't match, the update is rejected
        (another user modified it concurrently).
        
        Args:
            entity_type: Type of entity
            entity_id:   ID of entity to update
            data:        Fields to update (must include "version")
            actor:       Email of the updating user
            
        Returns:
            Updated entity as dict
            
        Raises:
            ValueError: If entity not found or validation fails
            ConflictError: If version mismatch (concurrent edit)
        """
        registry = self._get_registry(entity_type)
        model_class = registry["model_class"]
        container_name = registry["container"]
        
        # Load the current entity
        existing = self.get(entity_type, entity_id)
        if existing is None:
            logger.warning("update: %s '%s' not found", entity_type, entity_id)
            raise ValueError(
                f"{entity_type} '{entity_id}' not found"
            )
        
        # Optimistic locking: version is REQUIRED to prevent stale writes.
        # The client must send the version they loaded; if it doesn't
        # match, another user modified the entity concurrently.
        expected_version = data.get("version")
        if expected_version is None:
            logger.warning("update: missing version for %s '%s'", entity_type, entity_id)
            raise ValueError(
                f"'version' field is required for updates. "
                f"Load the entity first and include its version "
                f"in the update payload to enable conflict detection."
            )
        if existing["version"] != expected_version:
            logger.warning(
                "Version conflict: %s '%s' expected v%s, found v%s",
                entity_type, entity_id, expected_version, existing['version'],
            )
            raise ConflictError(
                f"Version conflict for {entity_type} '{entity_id}': "
                f"expected version {expected_version}, "
                f"found version {existing['version']}. "
                f"Another user may have modified this entity."
            )
        
        # Track changes for audit
        changes = {}
        for key, new_value in data.items():
            if key in ("version", "modifiedBy", "modifiedDate"):
                continue
            old_value = existing.get(key)
            if old_value != new_value:
                changes[key] = {"from": old_value, "to": new_value}
        
        # Merge updates into existing document
        merged = {**existing}
        for key, value in data.items():
            if key not in ("id", "createdBy", "createdDate"):
                merged[key] = value
        
        # Bump version and audit fields
        merged["version"] = existing["version"] + 1
        merged["modifiedBy"] = actor
        merged["modifiedDate"] = utc_now()
        
        # Validate the merged entity
        entity = model_class.from_dict(merged)
        errors = entity.validate()
        if errors:
            raise ValueError(
                f"Validation failed for {entity_type}: {errors}"
            )
        
        # Write to Cosmos DB (replace the entire document)
        container = self._cosmos.get_container(container_name)
        result = container.replace_item(
            item=entity_id,
            body=entity.to_dict()
        )
        
        # Generate audit entry
        if changes:
            self._create_audit_entry(
                action=AuditAction.UPDATE,
                entity_type=entity_type,
                entity_id=entity_id,
                actor=actor,
                changes=changes,
            )
        
        logger.info(
            "Updated %s '%s' (v%d → v%d), %d field(s) changed",
            entity_type, entity_id,
            existing['version'], merged['version'], len(changes),
        )
        return result
    
    # =========================================================================
    # DELETE
    # =========================================================================
    
    def delete(
        self,
        entity_type: str,
        entity_id: str,
        actor: str = "system",
        hard_delete: bool = False,
        version: Optional[int] = None
    ) -> bool:
        """
        Delete an entity.
        
        By default, performs a soft delete (sets status to "disabled").
        Pass hard_delete=True to permanently remove from the database.
        
        Before deleting, checks for cross-references. If the entity
        is still referenced by other entities, deletion is blocked
        with a clear error message.
        
        Args:
            entity_type: Type of entity
            entity_id:   ID of entity to delete
            actor:       Email of the deleting user
            hard_delete: If True, permanently remove; if False, disable
            version:     Expected version (optional optimistic lock)
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If entity not found or still referenced
            ConflictError: If version mismatch
        """
        existing = self.get(entity_type, entity_id)
        if existing is None:
            raise ValueError(
                f"{entity_type} '{entity_id}' not found"
            )
        
        # Optimistic locking (optional on delete, required on update)
        if version is not None and existing["version"] != version:
            raise ConflictError(
                f"Version conflict for {entity_type} '{entity_id}': "
                f"expected version {version}, "
                f"found version {existing['version']}."
            )
        
        # Block deletion if other entities still reference this one.
        refs = self.find_references(entity_type, entity_id)
        if refs:
            logger.warning(
                "delete blocked: %s '%s' still referenced by %s",
                entity_type, entity_id, refs,
            )
            ref_summary = "; ".join(
                f"{rtype}: {', '.join(rids)}" for rtype, rids in refs.items()
            )
            raise ValueError(
                f"Cannot delete {entity_type} '{entity_id}' because it is "
                f"still referenced by: {ref_summary}. "
                f"Remove those references first."
            )
        
        registry = self._get_registry(entity_type)
        container = self._cosmos.get_container(registry["container"])
        
        if hard_delete:
            # Permanent deletion
            container.delete_item(
                item=entity_id,
                partition_key=existing["status"]
            )
            action = AuditAction.DELETE
        else:
            # Soft delete: change status to disabled
            existing["status"] = EntityStatus.DISABLED
            existing["version"] = existing["version"] + 1
            existing["modifiedBy"] = actor
            existing["modifiedDate"] = utc_now()
            container.replace_item(
                item=entity_id,
                body=existing
            )
            action = AuditAction.DISABLE
        
        # Audit
        self._create_audit_entry(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            changes={
                "status": {
                    "from": existing.get("status", "active"),
                    "to": "deleted" if hard_delete else "disabled"
                }
            },
        )
        
        method = "hard deleted" if hard_delete else "disabled"
        logger.info(
            "%s %s '%s' (actor=%s)",
            method.capitalize(), entity_type, entity_id, actor,
        )
        return True
    
    # =========================================================================
    # COPY
    # =========================================================================
    
    def copy(
        self,
        entity_type: str,
        entity_id: str,
        actor: str = "system",
        new_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Clone an entity, creating a new copy with a new ID.
        
        Sets status to "staged" on the copy so it doesn't immediately
        become active.
        
        Args:
            entity_type: Type of entity
            entity_id:   ID of entity to copy
            actor:       Email of the copying user
            new_name:    Optional name for the copy (default: "Copy of {name}")
            
        Returns:
            New entity dict
        """
        existing = self.get(entity_type, entity_id)
        if existing is None:
            raise ValueError(
                f"{entity_type} '{entity_id}' not found"
            )
        
        registry = self._get_registry(entity_type)
        
        # Build the copy data
        copy_data = {**existing}
        copy_data["id"] = self._generate_id(registry["id_prefix"])
        copy_data["name"] = new_name or f"Copy of {existing.get('name', entity_id)}"
        copy_data["status"] = EntityStatus.STAGED  # Start in staged state
        copy_data["version"] = 1
        
        # Remove Cosmos DB metadata
        for meta_key in ("_rid", "_self", "_etag", "_attachments", "_ts"):
            copy_data.pop(meta_key, None)
        
        # Create the copy
        result = self.create(entity_type, copy_data, actor=actor)
        
        # Audit the copy
        self._create_audit_entry(
            action=AuditAction.COPY,
            entity_type=entity_type,
            entity_id=copy_data["id"],
            actor=actor,
            changes={"copiedFrom": {"from": None, "to": entity_id}},
        )
        
        logger.info(
            "Copied %s '%s' → '%s'", entity_type, entity_id, copy_data['id'],
        )
        return result
    
    # =========================================================================
    # STATUS MANAGEMENT
    # =========================================================================
    
    def set_status(
        self,
        entity_type: str,
        entity_id: str,
        new_status: str,
        actor: str = "system",
        version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Change an entity's status (active/disabled/staged).
        
        This is a convenience method that handles version bumping.
        If a version is provided by the caller it is used for
        optimistic locking; otherwise the current stored version
        is used (internal calls).
        
        Args:
            entity_type: Type of entity
            entity_id:   Entity ID
            new_status:  New status value
            actor:       User making the change
            version:     Expected version (caller-provided for locking)
            
        Returns:
            Updated entity dict
        """
        existing = self.get(entity_type, entity_id)
        if existing is None:
            raise ValueError(
                f"{entity_type} '{entity_id}' not found"
            )
        
        # Use caller version if provided, otherwise use current stored version
        expected_version = version if version is not None else existing["version"]
        
        return self.update(
            entity_type=entity_type,
            entity_id=entity_id,
            data={
                "status": new_status,
                "version": expected_version,
            },
            actor=actor
        )
    
    # =========================================================================
    # CROSS-REFERENCE QUERIES
    # =========================================================================
    
    def find_references(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, List[str]]:
        """
        Find all entities that reference the given entity.
        
        Used for "used in" display and safe deletion checks:
            - Rule: Which triggers reference this rule?
            - Action: Which routes use this action?
            - Route: Which triggers point to this route?
        
        Args:
            entity_type: Type of entity being referenced
            entity_id:   ID of the entity
            
        Returns:
            Dict of referencing entity type → list of referencing IDs
        """
        references = {}
        
        if entity_type == "rule":
            # Find triggers that reference this rule in their expressions
            triggers, _ = self.list("trigger")
            referencing_triggers = []
            for trigger_doc in triggers:
                trigger = Trigger.from_dict(trigger_doc)
                if entity_id in trigger.get_referenced_rule_ids():
                    referencing_triggers.append(trigger.id)
            if referencing_triggers:
                references["triggers"] = referencing_triggers
        
        elif entity_type == "action":
            # Find routes that include this action
            routes, _ = self.list("route")
            referencing_routes = []
            for route_doc in routes:
                route = Route.from_dict(route_doc)
                if entity_id in route.get_referenced_action_ids():
                    referencing_routes.append(route.id)
            if referencing_routes:
                references["routes"] = referencing_routes
        
        elif entity_type == "route":
            # Find triggers that point to this route
            triggers, _ = self.list("trigger")
            referencing_triggers = []
            for trigger_doc in triggers:
                if trigger_doc.get("onTrue") == entity_id:
                    referencing_triggers.append(trigger_doc["id"])
            if referencing_triggers:
                references["triggers"] = referencing_triggers
        
        return references
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _get_registry(self, entity_type: str) -> Dict:
        """Look up entity registry, raising ValueError for unknown types"""
        if entity_type not in ENTITY_REGISTRY:
            raise ValueError(
                f"Unknown entity type: '{entity_type}'. "
                f"Valid types: {list(ENTITY_REGISTRY.keys())}"
            )
        return ENTITY_REGISTRY[entity_type]
    
    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID with prefix: {prefix}-{short_uuid}"""
        short_uuid = str(uuid.uuid4())[:8]
        return f"{prefix}-{short_uuid}"
    
    def _create_audit_entry(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        actor: str,
        changes: Dict[str, Dict]
    ) -> None:
        """
        Create and store an audit entry in Cosmos DB.
        
        Args:
            action:      Operation performed
            entity_type: Type of entity
            entity_id:   ID of the entity
            actor:       User who made the change
            changes:     Dict of field changes {field: {from, to}}
        """
        entry = AuditEntry.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            changes=changes,
        )
        
        try:
            container = self._cosmos.get_container("audit-log")
            container.create_item(body=entry.to_dict())
        except Exception as e:
            # Audit failures should not block the main operation
            logger.warning("Failed to write audit entry: %s", e)


class ConflictError(Exception):
    """
    Raised when an optimistic locking conflict is detected.
    
    Occurs when User A fetches entity at version N, User B updates
    it to version N+1, then User A tries to save their changes
    with the stale version N.
    """
    pass
