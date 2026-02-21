"""
Cosmos DB Client for Field Portal
==================================

Provides access to the shared triage-management Cosmos DB database
for storing evaluations and corrections from the field portal wizard.

Reuses the triage system's CosmosDBConfig singleton so both systems
share one connection pool and one set of containers.

Containers used:
    - evaluations:  AI analysis stored after UAT creation (Step 9)
    - corrections:  User corrections to AI classifications (Step 4)

The triage system reads from these same containers to check for
existing evaluations (dedup) and to feed corrections into fine-tuning.
"""

import os
import sys
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger("field-portal.cosmos")

# Add project root to path for triage config access
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _get_cosmos():
    """
    Get the shared CosmosDBConfig singleton from the triage system.

    Returns:
        CosmosDBConfig instance

    Raises:
        ImportError: If triage config module is not available
    """
    from triage.config.cosmos_config import get_cosmos_config
    return get_cosmos_config()


# =============================================================================
# Evaluation Storage
# =============================================================================

def store_field_portal_evaluation(
    work_item_id: int,
    analysis: Dict[str, Any],
    original_input: Dict[str, Any],
    corrections: Optional[Dict[str, str]] = None,
    summary_html: str = "",
) -> Optional[str]:
    """
    Store a field portal AI evaluation in the shared evaluations container.

    Called after Step 9 (UAT creation) once we have the ADO work item ID.
    Uses the same evaluations container as the triage system so the triage
    pipeline can detect existing evaluations and skip re-analysis.

    The document uses `source: "field-portal"` to distinguish it from
    triage-generated evaluations (`source: "triage"`).

    Args:
        work_item_id:   ADO work item ID (partition key)
        analysis:       AI analysis dict (category, intent, confidence, etc.)
        original_input: Original submission (title, description, impact)
        corrections:    User corrections applied at Step 4 (if any)
        summary_html:   HTML summary written to ADO Challenge Details

    Returns:
        Evaluation ID on success, None on failure
    """
    try:
        cosmos = _get_cosmos()
        container = cosmos.get_container("evaluations")

        ts = datetime.now(timezone.utc)
        eval_id = f"eval-{work_item_id}-{ts.strftime('%Y%m%d%H%M%S')}"

        # Build evaluation document compatible with triage Evaluation model.
        # Triage-specific fields (ruleResults, matchedTrigger, etc.) are left
        # empty — the `source` field distinguishes field-portal evaluations.
        doc = {
            # Identity
            "id": eval_id,
            "workItemId": work_item_id,
            "date": ts.isoformat(),
            "evaluatedBy": "field-portal",
            "source": "field-portal",

            # AI classification results
            "category": analysis.get("category", ""),
            "intent": analysis.get("intent", ""),
            "confidence": analysis.get("confidence", 0),
            "businessImpact": analysis.get("business_impact", ""),
            "technicalComplexity": analysis.get("technical_complexity", ""),
            "urgencyLevel": analysis.get("urgency_level", ""),
            "reasoning": analysis.get("reasoning", ""),
            "domainEntities": analysis.get("domain_entities", {}),

            # Original submission context
            "originalTitle": original_input.get("title", ""),
            "originalDescription": original_input.get("description", ""),
            "originalImpact": original_input.get("impact", ""),

            # Corrections applied by the user (if any)
            "correctionsApplied": corrections or {},
            "hasCorrections": bool(corrections),

            # HTML summary (same content written to ADO)
            "summaryHtml": summary_html,

            # Triage-compatible fields (empty for field-portal source)
            "ruleResults": {},
            "skippedRules": [],
            "matchedTrigger": None,
            "appliedRoute": None,
            "actionsExecuted": [],
            "analysisState": "Approved",
            "fieldsChanged": {},
            "errors": [],
            "isDryRun": False,
        }

        container.create_item(body=doc)
        logger.info(
            "Stored field-portal evaluation %s for work item %d",
            eval_id, work_item_id,
        )
        return eval_id

    except Exception as e:
        logger.error(
            "Failed to store evaluation for work item %d: %s",
            work_item_id, e, exc_info=True,
        )
        return None


# =============================================================================
# Correction Storage
# =============================================================================

def store_correction(
    work_item_id: int,
    original_title: str,
    original_analysis: Dict[str, Any],
    corrections: Dict[str, str],
    notes: str = "",
    source: str = "field-portal",
) -> Optional[str]:
    """
    Store a user correction in Cosmos DB for fine-tuning consumption.

    Called when the user chooses "save_corrections" at Step 4. The
    fine-tuning engine reads from this container to improve AI accuracy.

    Args:
        work_item_id:      ADO work item ID (0 if not yet created)
        original_title:    Original submission title
        original_analysis: Original AI analysis before corrections
        corrections:       Dict of field → corrected value
        notes:             Free-text notes from the user
        source:            Origin system ("field-portal" or "triage")

    Returns:
        Correction ID on success, None on failure
    """
    try:
        cosmos = _get_cosmos()
        container = cosmos.get_container("corrections")

        ts = datetime.now(timezone.utc)
        correction_id = f"corr-{work_item_id}-{ts.strftime('%Y%m%d%H%M%S')}"

        doc = {
            "id": correction_id,
            "workItemId": work_item_id,
            "date": ts.isoformat(),
            "source": source,

            # What the AI originally predicted
            "originalTitle": original_title,
            "originalCategory": original_analysis.get("category", ""),
            "originalIntent": original_analysis.get("intent", ""),
            "originalConfidence": original_analysis.get("confidence", 0),
            "originalBusinessImpact": original_analysis.get("business_impact", ""),
            "originalTechnicalComplexity": original_analysis.get("technical_complexity", ""),
            "originalUrgencyLevel": original_analysis.get("urgency_level", ""),

            # What the user corrected
            "corrections": corrections,
            "notes": notes,

            # Metadata for fine-tuning pipeline
            "consumed": False,       # Set to True once the fine-tuning job picks it up
            "consumedDate": None,
        }

        container.create_item(body=doc)
        logger.info(
            "Stored correction %s for work item %d: %s",
            correction_id, work_item_id, corrections,
        )
        return correction_id

    except Exception as e:
        logger.error(
            "Failed to store correction for work item %d: %s",
            work_item_id, e, exc_info=True,
        )
        return None


# =============================================================================
# Query Helpers
# =============================================================================

def get_existing_evaluation(work_item_id: int) -> Optional[Dict[str, Any]]:
    """
    Check if an evaluation already exists for a work item.

    Used by the triage system to avoid re-evaluating items that were
    already classified during field portal submission.

    Args:
        work_item_id: ADO work item ID

    Returns:
        Most recent evaluation dict if found, None otherwise
    """
    try:
        cosmos = _get_cosmos()
        container = cosmos.get_container("evaluations")

        query = (
            "SELECT * FROM c "
            "WHERE c.workItemId = @wid "
            "ORDER BY c.date DESC "
            "OFFSET 0 LIMIT 1"
        )
        params = [{"name": "@wid", "value": work_item_id}]

        items = list(container.query_items(
            query=query,
            parameters=params,
            partition_key=work_item_id,
        ))
        return items[0] if items else None

    except Exception as e:
        logger.error(
            "Failed to query evaluation for work item %d: %s",
            work_item_id, e, exc_info=True,
        )
        return None


def get_corrections_for_work_item(work_item_id: int) -> List[Dict[str, Any]]:
    """
    Get all corrections for a specific work item.

    Args:
        work_item_id: ADO work item ID

    Returns:
        List of correction dicts, newest first
    """
    try:
        cosmos = _get_cosmos()
        container = cosmos.get_container("corrections")

        query = (
            "SELECT * FROM c "
            "WHERE c.workItemId = @wid "
            "ORDER BY c.date DESC"
        )
        params = [{"name": "@wid", "value": work_item_id}]

        return list(container.query_items(
            query=query,
            parameters=params,
            partition_key=work_item_id,
        ))

    except Exception as e:
        logger.error(
            "Failed to query corrections for work item %d: %s",
            work_item_id, e, exc_info=True,
        )
        return []
