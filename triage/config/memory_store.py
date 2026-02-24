"""
In-Memory Storage Backend
===========================

Provides an in-memory implementation of the Cosmos DB container interface
so the full triage system can run without a Cosmos DB endpoint configured.

When COSMOS_ENDPOINT is not set, the system automatically uses this backend.
All data lives in memory and is lost when the service stops — this is
intended for local development, demos, and UI testing only.

The InMemoryContainer class implements the same methods the CrudService,
AuditService, and EvaluationService call on Cosmos ContainerProxy objects:
    - create_item(body)
    - replace_item(item, body)
    - delete_item(item, partition_key)
    - query_items(query, parameters, ...)
    - read_item(item, partition_key)

Queries are handled by a simple evaluator that understands the subset of
Cosmos SQL used by the triage services (WHERE field = @param, ORDER BY,
OFFSET/LIMIT, cross-partition).
"""

import re
import copy
import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("triage.config.memory")


# =============================================================================
# In-Memory Container (mimics Cosmos ContainerProxy)
# =============================================================================

class InMemoryContainer:
    """
    In-memory stand-in for a Cosmos DB ContainerProxy.
    
    Stores items in a dict keyed by 'id'. Supports the subset of
    the Cosmos DB SDK surface that the triage services actually call.
    """
    
    def __init__(self, container_name: str, partition_key_path: str):
        """
        Args:
            container_name:    Name of the container (for logging)
            partition_key_path: e.g. "/status" — stored for reference
        """
        self.name = container_name
        self.partition_key_path = partition_key_path
        # Primary storage: dict of id → document
        self._items: Dict[str, Dict[str, Any]] = {}
    
    # ─── Write Operations ───────────────────────────────────────
    
    def create_item(self, body: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Insert a new item. Raises ValueError if ID already exists.
        
        Returns a copy of the stored document (like Cosmos does).
        """
        doc = copy.deepcopy(body)
        item_id = doc.get("id")
        
        if not item_id:
            raise ValueError("Document must have an 'id' field")
        
        if item_id in self._items:
            raise ValueError(
                f"Item with id '{item_id}' already exists in '{self.name}'"
            )
        
        # Add Cosmos-like metadata stubs
        doc["_ts"] = int(time.time())
        doc["_rid"] = f"mem-{item_id}"
        doc["_self"] = f"dbs/triage/colls/{self.name}/docs/{item_id}"
        doc["_etag"] = f"\"{hash(str(doc))}\""
        doc["_attachments"] = "attachments/"
        
        self._items[item_id] = doc
        return copy.deepcopy(doc)
    
    def replace_item(self, item: str, body: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Replace an existing item. Uses the `item` param as the ID.
        """
        doc = copy.deepcopy(body)
        item_id = item if isinstance(item, str) else body.get("id", item)
        
        if item_id not in self._items:
            raise ValueError(
                f"Item '{item_id}' not found in '{self.name}' for replace"
            )
        
        doc["_ts"] = int(time.time())
        doc["_etag"] = f"\"{hash(str(doc))}\""
        
        # Preserve original metadata
        for key in ("_rid", "_self", "_attachments"):
            if key not in doc and key in self._items[item_id]:
                doc[key] = self._items[item_id][key]
        
        self._items[item_id] = doc
        return copy.deepcopy(doc)
    
    def upsert_item(self, body: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Insert or replace an item based on its ID.
        """
        item_id = body.get("id")
        if item_id and item_id in self._items:
            return self.replace_item(item_id, body, **kwargs)
        return self.create_item(body, **kwargs)
    
    def delete_item(self, item: str, partition_key: str, **kwargs) -> None:
        """
        Remove an item by ID.
        """
        item_id = item if isinstance(item, str) else item
        if item_id in self._items:
            del self._items[item_id]
    
    # ─── Read Operations ────────────────────────────────────────
    
    def read_item(self, item: str, partition_key: str, **kwargs) -> Dict[str, Any]:
        """
        Read a single item by ID and partition key.
        """
        item_id = item if isinstance(item, str) else item
        if item_id not in self._items:
            raise Exception(f"(NotFound) Item '{item_id}' not found")
        return copy.deepcopy(self._items[item_id])
    
    def query_items(
        self,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
        partition_key: Optional[str] = None,
        enable_cross_partition_query: bool = False,
        max_item_count: int = 1000,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Execute a simplified SQL query against in-memory items.
        
        Supports the Cosmos SQL patterns used by the triage services:
            - SELECT * FROM c WHERE c.field = @param
            - SELECT * FROM c WHERE c.f1 = @p1 AND c.f2 = @p2
            - ORDER BY c.field ASC|DESC
            - Parameterized queries (@name style)
            - Partition key filtering
        """
        # Build a param lookup: @name → value
        param_map = {}
        if parameters:
            for p in parameters:
                param_map[p["name"]] = p["value"]
        
        # Start with all items
        items = list(self._items.values())
        
        # Apply partition key filter if provided
        if partition_key is not None:
            pk_field = self.partition_key_path.lstrip("/")
            items = [i for i in items if i.get(pk_field) == partition_key]
        
        # Parse WHERE conditions from the query
        items = self._apply_where(query, items, param_map)
        
        # Parse ORDER BY
        items = self._apply_order_by(query, items)
        
        # Limit
        items = items[:max_item_count]
        
        return [copy.deepcopy(i) for i in items]
    
    # ─── Query Helpers ──────────────────────────────────────────
    
    def _apply_where(
        self,
        query: str,
        items: List[Dict],
        param_map: Dict[str, Any]
    ) -> List[Dict]:
        """
        Parse WHERE clause and filter items.
        
        Handles:
            c.field = @param
            c.field != @param
            c.field LIKE @param  (simple prefix/suffix match)
            Multiple conditions joined by AND
        """
        # Extract WHERE clause content
        where_match = re.search(
            r'WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+OFFSET|\s*$)',
            query,
            re.IGNORECASE | re.DOTALL
        )
        if not where_match:
            return items
        
        where_clause = where_match.group(1).strip()
        
        # Split on AND (simple — doesn't handle nested OR/parens,
        # but the triage services only use AND conditions)
        conditions = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
        
        for cond in conditions:
            cond = cond.strip()
            items = self._eval_condition(cond, items, param_map)
        
        return items
    
    def _eval_condition(
        self,
        condition: str,
        items: List[Dict],
        param_map: Dict[str, Any]
    ) -> List[Dict]:
        """Evaluate a single WHERE condition and filter items."""
        
        # Pattern: c.field = @param  or  c.field != @param
        match = re.match(
            r'c\.(\w+)\s*(=|!=|<>|>=|<=|>|<)\s*(@\w+)',
            condition.strip()
        )
        if match:
            field, op, param_name = match.groups()
            value = param_map.get(param_name)
            
            def check(item):
                item_val = item.get(field)
                if op == '=': return item_val == value
                if op in ('!=', '<>'): return item_val != value
                if op == '>': return item_val is not None and item_val > value
                if op == '<': return item_val is not None and item_val < value
                if op == '>=': return item_val is not None and item_val >= value
                if op == '<=': return item_val is not None and item_val <= value
                return True
            
            return [i for i in items if check(i)]
        
        # Pattern: CONTAINS(c.field, @param) — case-insensitive text search
        contains_match = re.match(
            r'CONTAINS\s*\(\s*c\.(\w+)\s*,\s*(@\w+)(?:\s*,\s*true)?\s*\)',
            condition.strip(),
            re.IGNORECASE
        )
        if contains_match:
            field = contains_match.group(1)
            param_name = contains_match.group(2)
            value = str(param_map.get(param_name, "")).lower()
            return [
                i for i in items
                if value in str(i.get(field, "")).lower()
            ]
        
        # If we can't parse the condition, return all items (lenient)
        return items
    
    def _apply_order_by(self, query: str, items: List[Dict]) -> List[Dict]:
        """Parse ORDER BY clause and sort items."""
        order_match = re.search(
            r'ORDER\s+BY\s+c\.(\w+)(?:\s+(ASC|DESC))?',
            query,
            re.IGNORECASE
        )
        if not order_match:
            return items
        
        field = order_match.group(1)
        direction = (order_match.group(2) or "ASC").upper()
        reverse = direction == "DESC"
        
        return sorted(
            items,
            key=lambda i: (i.get(field) is None, i.get(field, "")),
            reverse=reverse
        )


# =============================================================================
# In-Memory Database (holds multiple containers)
# =============================================================================

class InMemoryDatabase:
    """
    Mimics a Cosmos DatabaseProxy, holding named containers.
    Pre-populates with seed data for a working demo experience.
    """
    
    def __init__(self, database_name: str):
        self.name = database_name
        self._containers: Dict[str, InMemoryContainer] = {}
    
    def get_container(self, container_name: str) -> InMemoryContainer:
        """Get a container by name (must exist)."""
        if container_name not in self._containers:
            raise ValueError(f"Container '{container_name}' not initialized")
        return self._containers[container_name]
    
    def create_container_if_not_exists(
        self,
        id: str,
        partition_key: Any = None,
        **kwargs
    ) -> InMemoryContainer:
        """Create a container if it doesn't exist yet."""
        if id not in self._containers:
            pk_path = "/id"
            if partition_key and hasattr(partition_key, 'path'):
                pk_path = partition_key.path
            elif isinstance(partition_key, str):
                pk_path = partition_key
            self._containers[id] = InMemoryContainer(id, pk_path)
        return self._containers[id]


# =============================================================================
# Seed Data
# =============================================================================
# Provides a realistic set of starter entities so the UI is immediately
# interactive without needing to manually create everything from scratch.

SEED_DATA = {
    "rules": [
        {
            "id": "rule-milestone-null",
            "name": "Milestone ID is Null",
            "description": "Detects work items with no milestone assigned",
            "field": "Custom.MilestoneID",
            "operator": "isNull",
            "value": None,
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "rule-area-unset",
            "name": "Area Path Not Set",
            "description": "Area path still at the root (unassigned)",
            "field": "System.AreaPath",
            "operator": "equals",
            "value": "Unified Action Tracker",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "rule-priority-high",
            "name": "Priority is High",
            "description": "Work item has priority 1 (Critical)",
            "field": "Microsoft.VSTS.Common.Priority",
            "operator": "equals",
            "value": "1",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "rule-state-new",
            "name": "State is New",
            "description": "Work item is in 'New' state",
            "field": "System.State",
            "operator": "equals",
            "value": "New",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "rule-tags-contain-triage",
            "name": "Tags Contain 'Triage'",
            "description": "Work item has the Triage tag",
            "field": "System.Tags",
            "operator": "contains",
            "value": "Triage",
            "status": "disabled",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        # ── Analysis Rules (evaluate AI analysis results) ──────────
        {
            "id": "rule-category-capacity",
            "name": "Category is Capacity",
            "description": "AI classified the item as a capacity request",
            "field": "Analysis.Category",
            "operator": "equals",
            "value": "capacity",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "rule-category-feature",
            "name": "Category is Feature Request",
            "description": "AI classified the item as a feature request",
            "field": "Analysis.Category",
            "operator": "equals",
            "value": "feature_request",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "rule-high-confidence",
            "name": "High Confidence (≥ 0.8)",
            "description": "AI analysis has high confidence in its classification",
            "field": "Analysis.Confidence",
            "operator": "gte",
            "value": "0.8",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "rule-high-urgency",
            "name": "Urgency is High",
            "description": "AI assessed high urgency level",
            "field": "Analysis.UrgencyLevel",
            "operator": "equals",
            "value": "high",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "rule-high-impact",
            "name": "Business Impact is High",
            "description": "AI assessed high business impact",
            "field": "Analysis.BusinessImpact",
            "operator": "equals",
            "value": "high",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
    ],
    "actions": [
        {
            "id": "action-set-triage-tag",
            "name": "Add Triage Tag",
            "description": "Appends 'AutoTriaged' to the Tags field",
            "field": "System.Tags",
            "operation": "append",
            "value": "; AutoTriaged",
            "valueType": "static",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "action-set-area-triage",
            "name": "Route to Triage Team",
            "description": "Moves item to the Triage area path",
            "field": "System.AreaPath",
            "operation": "set",
            "value": "Unified Action Tracker\\Triage",
            "valueType": "static",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "action-stamp-date",
            "name": "Stamp Triage Date",
            "description": "Sets a custom field to today's date",
            "field": "Custom.TriageDate",
            "operation": "set_computed",
            "value": "today",
            "valueType": "computed",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "action-add-comment",
            "name": "Add Triage Comment",
            "description": "Adds a templated comment to the work item",
            "field": "System.History",
            "operation": "template",
            "value": "Auto-triaged by the Triage Management System on {today()}. Work item #{WorkItemId} created by {CreatedBy}.",
            "valueType": "template",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
    ],
    "routes": [
        {
            "id": "route-standard-triage",
            "name": "Standard Triage Route",
            "description": "Tags, routes, stamps date, and comments",
            "actionIds": [
                "action-set-triage-tag",
                "action-set-area-triage",
                "action-stamp-date",
                "action-add-comment",
            ],
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "route-tag-only",
            "name": "Tag Only Route",
            "description": "Just adds the triage tag without routing",
            "actionIds": [
                "action-set-triage-tag",
            ],
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
    ],
    "triggers": [
        {
            "id": "dt-new-no-milestone",
            "name": "New Items Missing Milestone",
            "description": "Catches new work items that have no milestone set",
            "priority": 10,
            "expression": {
                "and": ["rule-state-new", "rule-milestone-null"]
            },
            "onTrue": "route-standard-triage",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
        {
            "id": "dt-unassigned-area",
            "name": "Unassigned Area Path",
            "description": "Routes items still at the root area path",
            "priority": 20,
            "expression": {
                "and": ["rule-area-unset"]
            },
            "onTrue": "route-tag-only",
            "status": "active",
            "version": 1,
            "createdBy": "system",
            "createdDate": "2026-02-10T00:00:00Z",
            "modifiedBy": "system",
            "modifiedDate": "2026-02-10T00:00:00Z",
        },
    ],
    "evaluations": [],
    "analysis-results": [],
    "field-schema": [
        # ── System Fields ──────────────────────────────────────────
        {
            "id": "System.AreaPath",
            "displayName": "Area Path",
            "type": "treePath",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "under", "startsWith", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Standard",
            "description": "Hierarchical area classification",
        },
        {
            "id": "System.IterationPath",
            "displayName": "Iteration Path",
            "type": "treePath",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "under", "startsWith", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Standard",
            "description": "Sprint / iteration assignment",
        },
        {
            "id": "System.State",
            "displayName": "State",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["New", "Active", "Resolved", "Closed", "Removed"],
            "required": True,
            "readOnly": False,
            "group": "Standard",
            "description": "Work item lifecycle state",
        },
        {
            "id": "System.WorkItemType",
            "displayName": "Work Item Type",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["Bug", "Task", "User Story", "Feature", "Epic", "Issue", "Action"],
            "required": True,
            "readOnly": True,
            "group": "Standard",
            "description": "Type of work item",
        },
        {
            "id": "System.AssignedTo",
            "displayName": "Assigned To",
            "type": "identity",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "isNull", "isNotNull", "in", "notIn"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Standard",
            "description": "Person the item is assigned to",
        },
        {
            "id": "System.CreatedBy",
            "displayName": "Created By",
            "type": "identity",
            "source": "ado",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Standard",
            "description": "Who created the work item",
        },
        {
            "id": "System.CreatedDate",
            "displayName": "Created Date",
            "type": "dateTime",
            "source": "ado",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "gt", "lt", "gte", "lte"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Standard",
            "description": "When the work item was created",
        },
        {
            "id": "System.ChangedDate",
            "displayName": "Changed Date",
            "type": "dateTime",
            "source": "ado",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "gt", "lt", "gte", "lte"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Standard",
            "description": "Last modification date",
        },
        {
            "id": "System.Title",
            "displayName": "Title",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "contains", "notContains", "startsWith", "matches"],
            "allowedValues": [],
            "required": True,
            "readOnly": False,
            "group": "Standard",
            "description": "Work item title",
        },
        {
            "id": "System.Description",
            "displayName": "Description",
            "type": "html",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Standard",
            "description": "Work item description (HTML)",
        },
        {
            "id": "System.Tags",
            "displayName": "Tags",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["contains", "notContains", "equals", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Standard",
            "description": "Semicolon-separated tag list",
        },
        {
            "id": "System.Reason",
            "displayName": "Reason",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Standard",
            "description": "Reason for the current state",
        },
        {
            "id": "Microsoft.VSTS.Common.Priority",
            "displayName": "Priority",
            "type": "integer",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "gt", "lt", "gte", "lte", "in", "notIn"],
            "allowedValues": ["1", "2", "3", "4"],
            "required": False,
            "readOnly": False,
            "group": "Planning",
            "description": "Priority (1=Critical, 4=Low)",
        },
        {
            "id": "Microsoft.VSTS.Common.Severity",
            "displayName": "Severity",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["1 - Critical", "2 - High", "3 - Medium", "4 - Low"],
            "required": False,
            "readOnly": False,
            "group": "Planning",
            "description": "Bug severity level",
        },
        {
            "id": "Microsoft.VSTS.Common.Triage",
            "displayName": "Triage",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["Pending", "More Info", "Info Received", "Triaged"],
            "required": False,
            "readOnly": False,
            "group": "Planning",
            "description": "Triage status",
        },
        {
            "id": "Microsoft.VSTS.Scheduling.Effort",
            "displayName": "Effort",
            "type": "double",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "gt", "lt", "gte", "lte", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Planning",
            "description": "Story points / effort estimate",
        },
        {
            "id": "Microsoft.VSTS.Common.ValueArea",
            "displayName": "Value Area",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["Architectural", "Business"],
            "required": False,
            "readOnly": False,
            "group": "Planning",
            "description": "Business vs Architectural value",
        },
        # ── Custom Fields ──────────────────────────────────────────
        {
            "id": "Custom.SolutionArea",
            "displayName": "Solution Area",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "contains", "in", "notIn", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Custom",
            "description": "Custom solution area classification",
        },
        {
            "id": "Custom.Milestone",
            "displayName": "Milestone",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "contains", "in", "notIn", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Custom",
            "description": "Project milestone",
        },
        {
            "id": "Custom.ROBAnalysisState",
            "displayName": "ROB Analysis State",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "in", "notIn", "isNull", "isNotNull"],
            "allowedValues": ["Not Started", "In Progress", "Completed", "Skipped"],
            "required": False,
            "readOnly": False,
            "group": "Custom",
            "description": "ROB analysis workflow state",
        },
        {
            "id": "Custom.TriageCategory",
            "displayName": "Triage Category",
            "type": "string",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "in", "notIn", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Custom",
            "description": "Triage classification category",
        },
        {
            "id": "Custom.ActionOwner",
            "displayName": "Action Owner",
            "type": "identity",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "isNull", "isNotNull", "in", "notIn"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Custom",
            "description": "Designated action owner",
        },
        {
            "id": "Custom.StatusDate",
            "displayName": "Status Date",
            "type": "dateTime",
            "source": "ado",
            "canEvaluate": True,
            "canSet": True,
            "operators": ["equals", "notEquals", "gt", "lt", "gte", "lte", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": False,
            "group": "Custom",
            "description": "Date of last status update",
        },
        # ── Analysis Fields (from AI analysis pipeline) ────────────
        {
            "id": "Analysis.Category",
            "displayName": "Analysis Category",
            "type": "string",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn", "contains", "isNull", "isNotNull"],
            "allowedValues": [
                "capacity", "feature_request", "bug_report", "configuration",
                "access_permission", "monitoring_alerting", "documentation",
                "security_compliance", "performance", "migration",
                "cost_optimization", "integration", "general_inquiry",
            ],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "AI-classified category of the work item",
        },
        {
            "id": "Analysis.Intent",
            "displayName": "Analysis Intent",
            "type": "string",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn", "contains", "isNull", "isNotNull"],
            "allowedValues": [
                "requesting_feature", "reporting_bug", "asking_question",
                "requesting_access", "requesting_capacity", "reporting_issue",
                "requesting_change", "providing_feedback",
            ],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "AI-inferred intent of the submitter",
        },
        {
            "id": "Analysis.Confidence",
            "displayName": "Analysis Confidence",
            "type": "double",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "gt", "lt", "gte", "lte"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "AI confidence score (0.0 – 1.0)",
        },
        {
            "id": "Analysis.Products",
            "displayName": "Detected Products",
            "type": "stringList",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Azure products mentioned in the work item",
        },
        {
            "id": "Analysis.Services",
            "displayName": "Azure & Modern Work Services",
            "type": "stringList",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Azure and Modern Work services identified in the work item",
        },
        {
            "id": "Analysis.Regions",
            "displayName": "Regions / Locations",
            "type": "stringList",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Geographic regions or Azure locations mentioned",
        },
        {
            "id": "Analysis.BusinessImpact",
            "displayName": "Business Impact",
            "type": "string",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["high", "medium", "low"],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "AI-assessed business impact level",
        },
        {
            "id": "Analysis.TechnicalComplexity",
            "displayName": "Technical Complexity",
            "type": "string",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["high", "medium", "low"],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "AI-assessed technical complexity",
        },
        {
            "id": "Analysis.UrgencyLevel",
            "displayName": "Urgency Level",
            "type": "string",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["high", "medium", "low"],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "AI-assessed urgency level",
        },
        {
            "id": "Analysis.Source",
            "displayName": "Analysis Source",
            "type": "string",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn"],
            "allowedValues": ["hybrid", "llm", "pattern", "fallback"],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Which engine produced the analysis (hybrid, llm, pattern)",
        },
        {
            "id": "Analysis.Agreement",
            "displayName": "Analysis Agreement",
            "type": "boolean",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals"],
            "allowedValues": ["true", "false"],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Whether pattern and LLM engines agree on classification",
        },
        {
            "id": "Analysis.ContextSummary",
            "displayName": "Context Summary",
            "type": "string",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "AI-generated summary of the work item context",
        },
        {
            "id": "Analysis.Technologies",
            "displayName": "Technologies",
            "type": "stringList",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Technologies referenced in the work item",
        },
        {
            "id": "Analysis.TechnicalAreas",
            "displayName": "Technical Areas",
            "type": "stringList",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Technical domain areas (networking, security, identity, etc.)",
        },
        {
            "id": "Analysis.ComplianceFrameworks",
            "displayName": "Compliance Frameworks",
            "type": "stringList",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Compliance or regulatory frameworks referenced (HIPAA, GDPR, SOC2, etc.)",
        },
        {
            "id": "Analysis.DiscoveredServices",
            "displayName": "Discovered Services",
            "type": "stringList",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["contains", "notContains", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Services discovered via dynamic/live lookup rather than static taxonomy",
        },
        {
            "id": "Analysis.PatternCategory",
            "displayName": "Pattern Category",
            "type": "string",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "in", "notIn", "isNull", "isNotNull"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Category from the pattern-matching engine (before LLM)",
        },
        {
            "id": "Analysis.PatternConfidence",
            "displayName": "Pattern Confidence",
            "type": "double",
            "source": "analysis",
            "canEvaluate": True,
            "canSet": False,
            "operators": ["equals", "notEquals", "gt", "lt", "gte", "lte"],
            "allowedValues": [],
            "required": False,
            "readOnly": True,
            "group": "Analysis",
            "description": "Confidence score from the pattern-matching engine",
        },
    ],
    "audit-log": [],
}


def seed_containers(containers: Dict[str, InMemoryContainer]) -> None:
    """
    Populate in-memory containers with seed data.
    
    Called once at startup when running in memory mode.
    Skips items that already exist (no-op for already seeded).
    """
    for container_name, items in SEED_DATA.items():
        if container_name not in containers:
            continue
        container = containers[container_name]
        for item in items:
            try:
                container.create_item(item)
            except ValueError:
                pass  # Already exists
    
    total = sum(len(v) for v in SEED_DATA.values())
    logger.info("Seeded %d items across %d containers", total, len(SEED_DATA))
