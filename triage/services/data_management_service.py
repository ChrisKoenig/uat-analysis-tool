"""
Data Management Service
========================

FR-2005 – Export and import Rules, Triggers, Routes, and Actions
between environments (or as backup/restore).

Key design decisions:
    - Match entities by **name** (natural key), not UUID
    - Import uses upsert: existing match → overwrite, else → create new
    - Auto-include dependencies:
        Trigger → Rules + Route; Route → Actions
    - Auto-backup current state before import (downloadable from audit log)
    - Import order: Rules → Actions → Routes → Triggers (leaves first)
    - Every export/import is audit-logged
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set, Tuple, cast

from ..config.cosmos_config import get_cosmos_config
from ..models.base import BaseEntity, EntityStatus, utc_now
from ..models.rule import Rule
from ..models.action import Action
from ..models.trigger import Trigger
from ..models.route import Route
from ..models.audit_entry import AuditEntry, AuditAction

logger = logging.getLogger("triage.services.data_management")

# Entity types that support export/import
EXPORTABLE_TYPES = ["rules", "actions", "routes", "triggers"]

# Maps plural container names to CRUD service entity type keys
CONTAINER_TO_TYPE = {
    "rules": "rule",
    "actions": "action",
    "routes": "route",
    "triggers": "trigger",
}

MODEL_CLASSES = {
    "rules": Rule,
    "actions": Action,
    "routes": Route,
    "triggers": Trigger,
}

# Cosmos metadata fields to strip from exports
COSMOS_META_KEYS = ("_rid", "_self", "_etag", "_attachments", "_ts")


class DataManagementService:
    """Export / import entities with dependency resolution and audit trail."""

    def __init__(self):
        self._cosmos = get_cosmos_config()

    # =========================================================================
    # EXPORT
    # =========================================================================

    def export_entities(
        self,
        selections: Dict[str, Optional[List[str]]],
        actor: str = "system",
    ) -> Dict[str, Any]:
        """
        Export selected entities with auto-included dependencies.

        Args:
            selections: e.g. {"rules": ["rule-abc"], "triggers": None}
                        None/empty list = export ALL of that type.
                        Omitted key = skip that type.
            actor: who initiated the export.

        Returns:
            Export bundle dict ready for JSON serialization.
        """
        # Phase 1 — gather requested entities
        collected: Dict[str, List[Dict]] = {t: [] for t in EXPORTABLE_TYPES}
        collected_ids: Dict[str, Set[str]] = {t: set() for t in EXPORTABLE_TYPES}

        for entity_type in EXPORTABLE_TYPES:
            if entity_type not in selections:
                continue
            ids = selections[entity_type]
            items = self._fetch_all(entity_type)
            if ids:
                items = [i for i in items if i["id"] in ids]
            for item in items:
                self._add_to_collected(item, entity_type, collected, collected_ids)

        # Phase 2 — auto-include dependencies
        dep_info = self._resolve_export_dependencies(collected, collected_ids)

        # Phase 3 — strip Cosmos metadata
        for entity_type in EXPORTABLE_TYPES:
            collected[entity_type] = [
                self._strip_cosmos_meta(doc) for doc in collected[entity_type]
            ]

        # Phase 4 — build bundle
        entity_counts = {t: len(collected[t]) for t in EXPORTABLE_TYPES if collected[t]}
        total = sum(entity_counts.values())

        bundle = {
            "metadata": {
                "exportDate": utc_now(),
                "exportedBy": actor,
                "entityCounts": entity_counts,
                "totalEntities": total,
                "formatVersion": "1.0",
            },
            "dependencies": dep_info,
        }
        for t in EXPORTABLE_TYPES:
            if collected[t]:
                bundle[t] = collected[t]

        # Phase 5 — audit
        self._audit(
            action="export",
            actor=actor,
            details={
                "entityCounts": entity_counts,
                "totalEntities": total,
            },
        )

        logger.info("Exported %d entities for %s", total, actor)
        return bundle

    # =========================================================================
    # IMPORT  —  preview
    # =========================================================================

    def preview_import(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse an export bundle and return a summary of what would happen.

        Returns dict with per-type counts of new / update / skip.
        """
        self._validate_bundle(bundle)

        preview: Dict[str, Any] = {}
        for entity_type in EXPORTABLE_TYPES:
            incoming = bundle.get(entity_type, [])
            if not incoming:
                continue

            existing_map = self._build_name_map(entity_type)
            new_count = 0
            update_count = 0
            items_preview = []

            for item in incoming:
                name = item.get("name", "")
                match = existing_map.get(name)
                action_label = "update" if match else "create"
                if match:
                    update_count += 1
                else:
                    new_count += 1
                items_preview.append({
                    "name": name,
                    "id": item.get("id", ""),
                    "status": item.get("status", ""),
                    "action": action_label,
                    "existingId": match["id"] if match else None,
                })

            preview[entity_type] = {
                "total": len(incoming),
                "new": new_count,
                "update": update_count,
                "items": items_preview,
            }

        return {
            "valid": True,
            "metadata": bundle.get("metadata", {}),
            "preview": preview,
        }

    # =========================================================================
    # IMPORT  —  execute
    # =========================================================================

    def execute_import(
        self,
        bundle: Dict[str, Any],
        selected: Optional[Dict[str, Optional[List[str]]]] = None,
        actor: str = "system",
    ) -> Dict[str, Any]:
        """
        Execute import with auto-backup, name-based upsert and audit.

        Args:
            bundle: the export bundle JSON.
            selected: optional per-type list of entity names to import.
                      None = import everything in the bundle.
            actor: who initiated the import.

        Returns:
            Result summary with created/updated/skipped counts.
        """
        self._validate_bundle(bundle)

        # Phase 1 — auto-backup of entity types that will be touched
        affected_types = [
            t for t in EXPORTABLE_TYPES if bundle.get(t)
        ]
        backup_bundle = self._create_backup(affected_types, actor)

        # Phase 2 — import in dependency order: Rules → Actions → Routes → Triggers
        import_order = ["rules", "actions", "routes", "triggers"]
        results: Dict[str, Dict[str, Any]] = {}
        id_remap: Dict[str, str] = {}  # old_id → new_id (for dependency rewiring)

        for entity_type in import_order:
            incoming = bundle.get(entity_type, [])
            if not incoming:
                continue

            # Apply selection filter if provided
            if selected and entity_type in selected:
                names_list = selected[entity_type]
                if names_list:
                    allowed_names = set(names_list)
                    incoming = [i for i in incoming if i.get("name") in allowed_names]

            if not incoming:
                continue

            type_result = self._import_entity_type(
                entity_type, incoming, id_remap, actor
            )
            results[entity_type] = type_result

        # Phase 3 — audit
        total_created = sum(r.get("created", 0) for r in results.values())
        total_updated = sum(r.get("updated", 0) for r in results.values())
        total_failed = sum(r.get("failed", 0) for r in results.values())

        self._audit(
            action="import",
            actor=actor,
            details={
                "results": results,
                "totalCreated": total_created,
                "totalUpdated": total_updated,
                "totalFailed": total_failed,
                "backupId": backup_bundle.get("metadata", {}).get("exportDate", ""),
                "sourceMetadata": bundle.get("metadata", {}),
            },
        )

        logger.info(
            "Import complete: %d created, %d updated, %d failed — actor=%s",
            total_created, total_updated, total_failed, actor,
        )

        return {
            "success": True,
            "results": results,
            "totals": {
                "created": total_created,
                "updated": total_updated,
                "failed": total_failed,
            },
            "backup": backup_bundle.get("metadata", {}),
        }

    # =========================================================================
    # BACKUP  (pre-import snapshot)
    # =========================================================================

    def _create_backup(
        self, entity_types: List[str], actor: str
    ) -> Dict[str, Any]:
        """Create a full backup of specified entity types (same format as export)."""
        selections: Dict[str, Optional[List[str]]] = {t: None for t in entity_types}
        backup = self.export_entities(selections, actor=f"{actor}/auto-backup")
        backup["metadata"]["isBackup"] = True
        backup["metadata"]["backupReason"] = "pre-import auto-backup"
        logger.info("Auto-backup created for types: %s", entity_types)
        return backup

    def get_backup_for_audit(self, audit_entry_id: str) -> Optional[Dict]:
        """
        Retrieve the backup bundle stored in an audit entry's details.
        (Future: could store backups in blob storage for large datasets.)
        """
        try:
            container = self._cosmos.get_container("audit-log")
            query = "SELECT * FROM c WHERE c.id = @id"
            params = [{"name": "@id", "value": audit_entry_id}]
            items = list(container.query_items(
                query=query, parameters=params,
                enable_cross_partition_query=True,
            ))
            if items:
                return items[0].get("details", {}).get("backup")
        except Exception as e:
            logger.warning("Could not retrieve backup: %s", e)
        return None

    # =========================================================================
    # INTERNAL — fetch / name-map / upsert
    # =========================================================================

    def _fetch_all(self, entity_type: str) -> List[Dict]:
        """Fetch all documents from a container (cross-partition)."""
        container = self._cosmos.get_container(entity_type)
        query = "SELECT * FROM c"
        return list(container.query_items(
            query=query, enable_cross_partition_query=True,
        ))

    def _build_name_map(self, entity_type: str) -> Dict[str, Dict]:
        """Build {name: document} map for existing entities of this type."""
        items = self._fetch_all(entity_type)
        name_map: Dict[str, Dict] = {}
        for item in items:
            name = item.get("name", "")
            if name:
                name_map[name] = item
        return name_map

    def _import_entity_type(
        self,
        entity_type: str,
        incoming: List[Dict],
        id_remap: Dict[str, str],
        actor: str,
    ) -> Dict[str, Any]:
        """Import a batch of entities of one type using name-based upsert."""
        container = self._cosmos.get_container(entity_type)
        existing_map = self._build_name_map(entity_type)
        entity_key = CONTAINER_TO_TYPE[entity_type]

        created = 0
        updated = 0
        failed = 0
        errors: List[str] = []

        for item in incoming:
            try:
                original_id = item.get("id", "")
                name = item.get("name", "")
                if not name:
                    errors.append(f"Skipped item with no name (id={original_id})")
                    failed += 1
                    continue

                # Strip Cosmos metadata
                doc = self._strip_cosmos_meta(item)

                # Rewire references to use remapped IDs
                doc = self._rewire_references(entity_type, doc, id_remap)

                existing = existing_map.get(name)

                if existing:
                    # UPDATE path — preserve existing ID, bump version
                    doc["id"] = existing["id"]
                    doc["version"] = existing.get("version", 1) + 1
                    doc["modifiedBy"] = actor
                    doc["modifiedDate"] = utc_now()
                    # Preserve original creation metadata
                    doc["createdBy"] = existing.get("createdBy", actor)
                    doc["createdDate"] = existing.get("createdDate", utc_now())

                    old_status = existing.get("status", "active")
                    new_status = doc.get("status", old_status)

                    if old_status != new_status:
                        # Cross-partition move: delete + create
                        container.delete_item(
                            item=existing["id"],
                            partition_key=old_status,
                        )
                        for mk in COSMOS_META_KEYS:
                            doc.pop(mk, None)
                        container.create_item(body=doc)
                    else:
                        container.replace_item(item=existing["id"], body=doc)

                    id_remap[original_id] = existing["id"]
                    updated += 1
                    logger.debug("Updated %s '%s' (%s)", entity_type, name, existing["id"])

                else:
                    # CREATE path — generate new ID
                    from .crud_service import ENTITY_REGISTRY
                    prefix = ENTITY_REGISTRY[entity_key]["id_prefix"]
                    new_id = f"{prefix}-{str(uuid.uuid4())[:8]}"
                    doc["id"] = new_id
                    doc["version"] = 1
                    doc["createdBy"] = actor
                    doc["createdDate"] = utc_now()
                    doc["modifiedBy"] = actor
                    doc["modifiedDate"] = utc_now()
                    doc.setdefault("status", EntityStatus.ACTIVE)

                    container.create_item(body=doc)
                    id_remap[original_id] = new_id
                    created += 1
                    logger.debug("Created %s '%s' (%s)", entity_type, name, new_id)

            except Exception as e:
                name = item.get("name", item.get("id", "unknown"))
                logger.warning("Failed to import %s '%s': %s", entity_type, name, e)
                errors.append(f"{name}: {str(e)}")
                failed += 1

        result: Dict[str, Any] = {"created": created, "updated": updated, "failed": failed}
        if errors:
            result["errors"] = errors
        return result

    def _rewire_references(
        self, entity_type: str, doc: Dict, id_remap: Dict[str, str]
    ) -> Dict:
        """Update cross-entity ID references using the remap table."""
        if entity_type == "triggers":
            # Rewire expression tree rule IDs
            if "expression" in doc:
                doc["expression"] = self._rewire_expression(doc["expression"], id_remap)
            # Rewire onTrue route ID
            if "onTrue" in doc and doc["onTrue"] in id_remap:
                doc["onTrue"] = id_remap[doc["onTrue"]]

        elif entity_type == "routes":
            # Rewire action IDs
            if "actions" in doc:
                doc["actions"] = [
                    id_remap.get(aid, aid) for aid in doc["actions"]
                ]

        return doc

    def _rewire_expression(self, expr: Any, id_remap: Dict[str, str]) -> Any:
        """Recursively rewire rule IDs in a trigger expression tree."""
        if isinstance(expr, str):
            return id_remap.get(expr, expr)
        if isinstance(expr, dict):
            key = list(expr.keys())[0]
            if key == "not":
                return {"not": self._rewire_expression(expr["not"], id_remap)}
            elif key in ("and", "or"):
                return {key: [self._rewire_expression(c, id_remap) for c in expr[key]]}
        return expr

    # =========================================================================
    # DEPENDENCY RESOLUTION (for export)
    # =========================================================================

    def _resolve_export_dependencies(
        self,
        collected: Dict[str, List[Dict]],
        collected_ids: Dict[str, Set[str]],
    ) -> List[Dict[str, str]]:
        """
        For each trigger/route in collected, auto-include referenced entities.
        Returns a list of dependency-info dicts for the UI.
        """
        dep_info: List[Dict[str, str]] = []

        # Triggers → Rules + Route
        for trigger_doc in list(collected.get("triggers", [])):
            trigger = cast(Trigger, Trigger.from_dict(trigger_doc))
            # Referenced rules
            for rule_id in trigger.get_referenced_rule_ids():
                if rule_id not in collected_ids["rules"]:
                    rule_doc = self._fetch_by_id("rules", rule_id)
                    if rule_doc:
                        self._add_to_collected(rule_doc, "rules", collected, collected_ids)
                        dep_info.append({
                            "type": "rules",
                            "id": rule_id,
                            "name": rule_doc.get("name", rule_id),
                            "requiredBy": f"trigger:{trigger.name}",
                            "reason": "Referenced in expression tree",
                        })

            # Referenced route
            route_id: Optional[str] = trigger.get_referenced_route_id()
            if route_id and route_id not in collected_ids["routes"]:
                route_doc = self._fetch_by_id("routes", route_id)
                if route_doc:
                    self._add_to_collected(route_doc, "routes", collected, collected_ids)
                    dep_info.append({
                        "type": "routes",
                        "id": route_id,
                        "name": route_doc.get("name", route_id),
                        "requiredBy": f"trigger:{trigger.name}",
                        "reason": "onTrue route reference",
                    })

        # Routes → Actions
        for route_doc in list(collected.get("routes", [])):
            route = cast(Route, Route.from_dict(route_doc))
            for action_id in route.get_referenced_action_ids():
                if action_id not in collected_ids["actions"]:
                    action_doc = self._fetch_by_id("actions", action_id)
                    if action_doc:
                        self._add_to_collected(action_doc, "actions", collected, collected_ids)
                        dep_info.append({
                            "type": "actions",
                            "id": action_id,
                            "name": action_doc.get("name", action_id),
                            "requiredBy": f"route:{route.name}",
                            "reason": "Referenced in action list",
                        })

        return dep_info

    def _fetch_by_id(self, entity_type: str, entity_id: str) -> Optional[Dict]:
        """Fetch a single entity by ID (cross-partition)."""
        container = self._cosmos.get_container(entity_type)
        query = "SELECT * FROM c WHERE c.id = @id"
        params = [{"name": "@id", "value": entity_id}]
        items = list(container.query_items(
            query=query, parameters=params,
            enable_cross_partition_query=True,
        ))
        return items[0] if items else None

    def _add_to_collected(
        self,
        doc: Dict,
        entity_type: str,
        collected: Dict[str, List[Dict]],
        collected_ids: Dict[str, Set[str]],
    ) -> None:
        """Add a document to the collected set if not already present."""
        doc_id = doc.get("id", "")
        if doc_id and doc_id not in collected_ids[entity_type]:
            collected[entity_type].append(doc)
            collected_ids[entity_type].add(doc_id)

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _strip_cosmos_meta(self, doc: Dict) -> Dict:
        """Remove Cosmos DB internal metadata fields."""
        return {k: v for k, v in doc.items() if k not in COSMOS_META_KEYS}

    def _validate_bundle(self, bundle: Dict[str, Any]) -> None:
        """Basic validation of an import bundle."""
        if not isinstance(bundle, dict):
            raise ValueError("Import bundle must be a JSON object")
        if "metadata" not in bundle:
            raise ValueError("Import bundle missing 'metadata' section")
        has_entities = any(bundle.get(t) for t in EXPORTABLE_TYPES)
        if not has_entities:
            raise ValueError(
                "Import bundle contains no entity data. "
                f"Expected at least one of: {EXPORTABLE_TYPES}"
            )

    def _audit(self, action: str, actor: str, details: Dict) -> None:
        """Write an audit entry for an export/import operation."""
        entry = AuditEntry.create(
            action=f"data_management.{action}",
            entity_type="data_management",
            entity_id=f"dm-{str(uuid.uuid4())[:8]}",
            actor=actor,
            changes={},
        )
        entry.details = json.dumps(details, default=str)
        try:
            container = self._cosmos.get_container("audit-log")
            container.create_item(body=entry.to_dict())
        except Exception as e:
            logger.warning("Failed to write data-management audit entry: %s", e)
