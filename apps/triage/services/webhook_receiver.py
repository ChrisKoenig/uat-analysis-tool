"""
ADO Service Hook Webhook Receiver
===================================

Receives webhook notifications from Azure DevOps Service Hooks
when work items are created or updated in the target project.

ADO Service Hooks Configuration:
    1. Go to Project Settings → Service Hooks → New Subscription
    2. Select "Web Hooks" as the service
    3. Trigger: "Work item created" or "Work item updated"
    4. Filters:
        - Work item type = Action
        - Area Path UNDER the triage scope (e.g., "UAT\\MCAPS")
    5. Action:
        - URL: https://{host}:8009/api/v1/webhook/workitem
        - HTTP headers: (none needed — we validate via payload structure)
        - Resource details to send: All

Payload Structure (ADO Service Hook):
    ADO sends a JSON payload with this structure:
    {
        "subscriptionId": "...",
        "notificationId": 1,
        "eventType": "workitem.created" | "workitem.updated",
        "resource": {
            "id": 12345,
            "rev": 3,
            "fields": {
                "System.Id": 12345,
                "System.Title": "...",
                "System.AreaPath": "...",
                ...
            },
            "revision": { ... },       // For updates: current revision
            "revisedBy": { ... },       // Who triggered the change
        },
        "resourceContainers": {
            "project": { "id": "..." },
            "collection": { "id": "..." },
        },
        "message": { "text": "...", "html": "..." }
    }

Security Notes:
    - ADO Service Hooks support Basic Auth and HMAC validation
    - For Phase 2, we validate by checking the payload structure
    - Production: Add HMAC signature validation via shared secret
    - The webhook endpoint is rate-limited by FastAPI middleware
"""

import hmac
import hashlib
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("triage.services.webhook")


# =============================================================================
# Webhook Payload Models
# =============================================================================

class WebhookResourceFields(BaseModel):
    """
    Subset of the work item fields sent in the webhook payload.
    
    ADO sends different fields depending on the Service Hook configuration.
    We extract the ones we need for triage evaluation.
    """
    model_config = ConfigDict(extra="allow")


class WebhookResource(BaseModel):
    """
    The 'resource' section of an ADO Service Hook payload.
    
    Contains the work item data that was created or modified.
    For 'workitem.updated' events, also includes the changed fields.
    """
    id: int = Field(..., description="Work item ID")
    rev: Optional[int] = Field(None, description="Work item revision")
    fields: Optional[Dict[str, Any]] = Field(
        None, description="Work item fields (for workitem.created)"
    )
    # For workitem.updated, fields may be in 'revision' instead
    revision: Optional[Dict[str, Any]] = Field(
        None, description="Current revision (for workitem.updated)"
    )
    model_config = ConfigDict(extra="allow")


class WebhookPayload(BaseModel):
    """
    Complete ADO Service Hook webhook payload.
    
    This models the JSON body that ADO POSTs to our webhook endpoint
    when a subscribed event occurs.
    
    Event Types:
        - workitem.created:  New work item created
        - workitem.updated:  Existing work item modified
    """
    subscriptionId: Optional[str] = Field(
        None, description="Service Hook subscription ID"
    )
    notificationId: Optional[int] = Field(
        None, description="Notification sequence number"
    )
    eventType: str = Field(
        ..., description="Event type: 'workitem.created' or 'workitem.updated'"
    )
    resource: WebhookResource = Field(
        ..., description="Work item resource data"
    )
    resourceContainers: Optional[Dict[str, Any]] = Field(
        None, description="Project/collection metadata"
    )
    message: Optional[Dict[str, str]] = Field(
        None, description="Human-readable event message"
    )
    
    model_config = ConfigDict(extra="allow")


# =============================================================================
# Webhook Processing
# =============================================================================

class WebhookProcessor:
    """
    Processes incoming ADO Service Hook webhook notifications.
    
    The processor:
        1. Validates the webhook payload structure
        2. Extracts work item ID and fields from the payload
        3. Determines whether the item should be evaluated
        4. Triggers the evaluation pipeline (or queues it)
    
    Filtering Logic:
        Not all work item updates should trigger re-evaluation. We skip:
        - Updates that only changed Discussion (comment-only updates)
        - Updates where ROBAnalysisState is in a terminal state
          (Approved, Override) — those are done
        - Updates made by the triage system itself (avoid loops)
    
    Loop Prevention:
        When the triage system updates a work item (sets fields, posts
        comments), ADO fires another webhook. We detect self-triggered
        updates by checking the revisedBy identity against the service
        account, and skip them.
    
    Usage:
        processor = WebhookProcessor()
        
        # From the webhook endpoint handler:
        result = processor.process(payload)
        if result['should_evaluate']:
            eval_service.evaluate(result['work_item_id'], ...)
    """
    
    # States where re-evaluation should NOT happen (human has decided)
    TERMINAL_STATES = {"Approved", "Override"}
    
    # Fields that, when changed alone, do NOT warrant re-evaluation
    # (e.g., someone just added a comment)
    IGNORE_ONLY_FIELDS = {
        "System.History",         # Discussion/comments
        "System.Rev",             # Revision count (always changes)
        "System.ChangedDate",     # Timestamp (always changes)
        "System.ChangedBy",       # Who changed (always changes)
        "System.Watermark",       # Internal tracking
    }
    
    # Service account identifier for loop prevention
    # TODO: Update this when a managed identity / service principal is configured
    SERVICE_ACCOUNT = "triage-system"
    
    def __init__(self, shared_secret: Optional[str] = None):
        """
        Initialize the webhook processor.
        
        Args:
            shared_secret: Optional HMAC shared secret for payload validation.
                           If set, incoming webhooks must include a valid
                           X-Hub-Signature header.
        """
        self._shared_secret = shared_secret
        self._processed_count = 0
        self._skipped_count = 0
    
    def validate_signature(
        self,
        payload_bytes: bytes,
        signature_header: Optional[str]
    ) -> bool:
        """
        Validate the webhook HMAC signature.
        
        ADO Service Hooks can be configured to send a signature
        header for payload integrity verification.
        
        Args:
            payload_bytes:    Raw request body bytes
            signature_header: Value of X-Hub-Signature header
            
        Returns:
            True if signature is valid (or if no shared secret is configured)
        """
        # If no shared secret configured, skip validation
        if not self._shared_secret:
            return True
        
        if not signature_header:
            return False
        
        # Compute expected HMAC-SHA256
        expected = hmac.new(
            self._shared_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(f"sha256={expected}", signature_header)
    
    def process(self, payload: WebhookPayload) -> Dict[str, Any]:
        """
        Process an incoming webhook notification.
        
        Analyzes the payload and determines whether the work item
        should be evaluated through the triage pipeline.
        
        Args:
            payload: Parsed WebhookPayload from the request body
            
        Returns:
            Dict with keys:
                should_evaluate (bool):  Whether to trigger evaluation
                work_item_id (int):      ADO work item ID
                event_type (str):        The ADO event type
                skip_reason (str):       Why evaluation was skipped (if skipped)
                fields (Dict):           Extracted fields (if available in payload)
                revision (int):          Work item revision
                received_at (str):       ISO timestamp of processing
        """
        result = {
            "should_evaluate": False,
            "work_item_id": payload.resource.id,
            "event_type": payload.eventType,
            "skip_reason": None,
            "fields": {},
            "revision": payload.resource.rev,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        
        logger.debug(
            "process: event=%s, item=%d, rev=%s",
            payload.eventType, payload.resource.id, payload.resource.rev,
        )
        
        # =================================================================
        # Step 1: Validate event type
        # =================================================================
        valid_events = {"workitem.created", "workitem.updated"}
        if payload.eventType not in valid_events:
            result["skip_reason"] = (
                f"Unsupported event type: {payload.eventType}"
            )
            logger.debug("  skip: unsupported event type %s", payload.eventType)
            self._skipped_count += 1
            return result
        
        # =================================================================
        # Step 2: Extract fields from payload
        # =================================================================
        fields = self._extract_fields(payload)
        result["fields"] = fields
        
        # =================================================================
        # Step 3: Check for self-triggered update (loop prevention)
        # =================================================================
        if self._is_self_triggered(payload, fields):
            result["skip_reason"] = "Self-triggered update (loop prevention)"
            self._skipped_count += 1
            return result
        
        # =================================================================
        # Step 4: Check terminal state
        # =================================================================
        analysis_state = fields.get("Custom.ROBAnalysisState", "")
        if analysis_state in self.TERMINAL_STATES:
            result["skip_reason"] = (
                f"Work item in terminal state: {analysis_state}"
            )
            self._skipped_count += 1
            return result
        
        # =================================================================
        # Step 5: For updates, check if meaningful fields changed
        # =================================================================
        if payload.eventType == "workitem.updated":
            if not self._has_meaningful_changes(payload):
                result["skip_reason"] = (
                    "No meaningful field changes detected "
                    "(only metadata/discussion updated)"
                )
                self._skipped_count += 1
                return result
        
        # =================================================================
        # Step 6: All checks passed — should evaluate
        # =================================================================
        result["should_evaluate"] = True
        self._processed_count += 1
        
        logger.info(
            "%s for item %d → will evaluate",
            payload.eventType, payload.resource.id,
        )
        
        return result
    
    def _extract_fields(self, payload: WebhookPayload) -> Dict[str, Any]:
        """
        Extract work item fields from the webhook payload.
        
        ADO puts fields in different locations depending on event type:
            - workitem.created: resource.fields
            - workitem.updated: resource.revision.fields (sometimes)
            - Both may include resource.fields at the top level
        
        Note: Webhook payloads may not include ALL fields. The evaluation
        pipeline should re-fetch the work item via the REST API to get
        complete field data.
        
        Args:
            payload: Webhook payload
            
        Returns:
            Dict of field reference names to values
        """
        fields = {}
        
        # Primary source: resource.fields
        if payload.resource.fields:
            fields.update(payload.resource.fields)
        
        # Secondary source: resource.revision (for updates)
        if payload.resource.revision and isinstance(payload.resource.revision, dict):
            revision_fields = payload.resource.revision.get("fields", {})
            if revision_fields:
                fields.update(revision_fields)
        
        return fields
    
    def _is_self_triggered(
        self,
        payload: WebhookPayload,
        fields: Dict[str, Any]
    ) -> bool:
        """
        Determine if this webhook was triggered by the triage system itself.
        
        When the triage system updates a work item (setting fields,
        posting comments), ADO fires a webhook. We need to detect
        and skip these to avoid infinite evaluation loops.
        
        Detection strategy:
            1. Check System.ChangedBy against our service account
            2. Check revisedBy identity in the resource
        
        Args:
            payload: Webhook payload
            fields:  Extracted fields
            
        Returns:
            True if this update was made by the triage system
        """
        # Check ChangedBy field
        changed_by = fields.get("System.ChangedBy", "")
        if isinstance(changed_by, dict):
            # ADO sometimes returns identity objects
            changed_by = changed_by.get("uniqueName", changed_by.get("displayName", ""))
        
        if self.SERVICE_ACCOUNT.lower() in str(changed_by).lower():
            return True
        
        # Check revisedBy in the resource (for update events)
        resource_dict = payload.resource.model_dump() if hasattr(payload.resource, 'model_dump') else {}
        revised_by = resource_dict.get("revisedBy", {})
        if isinstance(revised_by, dict):
            revised_name = revised_by.get("uniqueName", revised_by.get("displayName", ""))
            if self.SERVICE_ACCOUNT.lower() in str(revised_name).lower():
                return True
        
        return False
    
    def _has_meaningful_changes(self, payload: WebhookPayload) -> bool:
        """
        For update events, check if any meaningful fields changed.
        
        ADO sends webhooks for every field change, including metadata
        updates (ChangedDate, Rev, etc.) and discussion-only changes.
        We only want to re-evaluate when substantive fields change.
        
        Strategy:
            If the payload includes changed fields information, check
            whether any are outside the IGNORE_ONLY_FIELDS set.
            If we can't determine what changed, default to evaluating
            (safe fallback — evaluation is idempotent).
        
        Args:
            payload: Webhook payload with update information
            
        Returns:
            True if meaningful changes detected (or if unknown)
        """
        # Try to extract changed fields from the payload
        # ADO includes 'resource.fields' with current values
        # and sometimes 'resource.revision' with the delta
        
        resource_dict = payload.resource.model_dump() if hasattr(payload.resource, 'model_dump') else {}
        
        # Some ADO webhook configs include 'changedFields' in the resource
        changed_fields = resource_dict.get("changedFields", {})
        
        if not changed_fields:
            # Can't determine what changed — evaluate to be safe
            return True
        
        # Check if any changed field is meaningful
        meaningful = set(changed_fields.keys()) - self.IGNORE_ONLY_FIELDS
        return len(meaningful) > 0
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get webhook processing statistics.
        
        Returns:
            Dict with processed and skipped counts
        """
        return {
            "processed": self._processed_count,
            "skipped": self._skipped_count,
            "total": self._processed_count + self._skipped_count,
        }
