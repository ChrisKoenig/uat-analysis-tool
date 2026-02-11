"""
Phase 2 Unit Tests: Webhook Receiver
======================================

Tests for the ADO Service Hook webhook processor
(triage/services/webhook_receiver.py).

Test Groups:
    1. Payload Parsing:     WebhookPayload model validation
    2. Event Filtering:     Valid/invalid event types
    3. Field Extraction:    Fields from resource.fields and resource.revision
    4. Loop Prevention:     Self-triggered update detection
    5. Terminal States:     Skip items in Approved/Override states
    6. Meaningful Changes:  Detect metadata-only vs. substantive updates
    7. Full Pipeline:       End-to-end process() calls
    8. HMAC Validation:     Signature verification
    9. Statistics:           Processed/skipped counters
"""

import pytest
import hmac
import hashlib
import json

from triage.services.webhook_receiver import (
    WebhookProcessor,
    WebhookPayload,
    WebhookResource,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def processor():
    """Fresh webhook processor"""
    return WebhookProcessor()


@pytest.fixture
def processor_with_secret():
    """Processor with HMAC shared secret"""
    return WebhookProcessor(shared_secret="test-secret-key")


def _make_payload(
    event_type="workitem.created",
    work_item_id=12345,
    fields=None,
    revision=None,
    extra_resource=None,
) -> WebhookPayload:
    """
    Build a WebhookPayload for testing.
    
    Args:
        event_type:     ADO event type
        work_item_id:   Work item ID
        fields:         Field dict (or None for default)
        revision:       Revision dict (or None)
        extra_resource: Extra keys for the resource dict
    """
    if fields is None:
        fields = {
            "System.Id": work_item_id,
            "System.Title": "Test Item",
            "System.AreaPath": "UAT\\MCAPS\\AI",
            "Custom.ROBAnalysisState": "Pending",
            "System.ChangedBy": "user@microsoft.com",
        }
    
    resource_data = {
        "id": work_item_id,
        "rev": 3,
        "fields": fields,
    }
    if revision:
        resource_data["revision"] = revision
    if extra_resource:
        resource_data.update(extra_resource)
    
    return WebhookPayload(
        subscriptionId="sub-001",
        notificationId=1,
        eventType=event_type,
        resource=WebhookResource(**resource_data),
        message={"text": f"Action {work_item_id} was created"},
    )


# =============================================================================
# 1. Payload Parsing Tests
# =============================================================================

class TestPayloadParsing:
    """Test WebhookPayload model validation"""
    
    def test_valid_created_payload(self):
        """Valid workitem.created payload parses correctly"""
        payload = _make_payload(event_type="workitem.created")
        assert payload.eventType == "workitem.created"
        assert payload.resource.id == 12345
    
    def test_valid_updated_payload(self):
        """Valid workitem.updated payload parses correctly"""
        payload = _make_payload(event_type="workitem.updated")
        assert payload.eventType == "workitem.updated"
    
    def test_resource_fields(self):
        """Resource contains fields dict"""
        payload = _make_payload()
        assert payload.resource.fields is not None
        assert "System.Title" in payload.resource.fields
    
    def test_optional_metadata(self):
        """Optional fields default to None"""
        payload = WebhookPayload(
            eventType="workitem.created",
            resource=WebhookResource(id=1),
        )
        assert payload.subscriptionId is None
        assert payload.notificationId is None
        assert payload.message is None
    
    def test_extra_fields_allowed(self):
        """Extra fields in payload are ignored (Config.extra='allow')"""
        payload = WebhookPayload(
            eventType="workitem.created",
            resource=WebhookResource(id=1),
            detailedMessage={"html": "<p>Extra</p>"},
        )
        assert payload.resource.id == 1


# =============================================================================
# 2. Event Filtering Tests
# =============================================================================

class TestEventFiltering:
    """Test event type validation"""
    
    def test_created_accepted(self, processor):
        """workitem.created is accepted"""
        payload = _make_payload(event_type="workitem.created")
        result = processor.process(payload)
        assert result["should_evaluate"] is True
    
    def test_updated_accepted(self, processor):
        """workitem.updated is accepted"""
        payload = _make_payload(event_type="workitem.updated")
        result = processor.process(payload)
        assert result["should_evaluate"] is True
    
    def test_deleted_rejected(self, processor):
        """workitem.deleted is not a valid trigger"""
        payload = _make_payload(event_type="workitem.deleted")
        result = processor.process(payload)
        assert result["should_evaluate"] is False
        assert "Unsupported event type" in result["skip_reason"]
    
    def test_comment_event_rejected(self, processor):
        """workitem.commented is not supported"""
        payload = _make_payload(event_type="workitem.commented")
        result = processor.process(payload)
        assert result["should_evaluate"] is False


# =============================================================================
# 3. Field Extraction Tests
# =============================================================================

class TestFieldExtraction:
    """Test field extraction from payloads"""
    
    def test_fields_from_resource(self, processor):
        """Fields extracted from resource.fields"""
        payload = _make_payload(
            fields={"System.Title": "From Fields", "Custom.Foo": "Bar"}
        )
        result = processor.process(payload)
        
        assert result["fields"]["System.Title"] == "From Fields"
        assert result["fields"]["Custom.Foo"] == "Bar"
    
    def test_fields_from_revision(self, processor):
        """For updates, fields merged from resource.revision"""
        payload = _make_payload(
            fields={"System.Title": "Original"},
            revision={"fields": {"System.Title": "Updated", "Custom.New": "value"}},
        )
        result = processor.process(payload)
        
        # revision.fields should override resource.fields
        assert result["fields"]["System.Title"] == "Updated"
        assert result["fields"]["Custom.New"] == "value"
    
    def test_no_fields(self, processor):
        """Payload with no fields still processes"""
        payload = WebhookPayload(
            eventType="workitem.created",
            resource=WebhookResource(id=999),
        )
        result = processor.process(payload)
        assert result["fields"] == {}


# =============================================================================
# 4. Loop Prevention Tests
# =============================================================================

class TestLoopPrevention:
    """Test self-triggered update detection"""
    
    def test_self_triggered_by_changed_by(self, processor):
        """Skip if ChangedBy matches service account"""
        payload = _make_payload(
            event_type="workitem.updated",
            fields={
                "System.ChangedBy": "triage-system",
                "Custom.ROBAnalysisState": "Pending",
            },
        )
        result = processor.process(payload)
        
        assert result["should_evaluate"] is False
        assert "loop prevention" in result["skip_reason"].lower()
    
    def test_self_triggered_by_identity_object(self, processor):
        """Handle ChangedBy as identity dict"""
        payload = _make_payload(
            event_type="workitem.updated",
            fields={
                "System.ChangedBy": {
                    "displayName": "Triage System Bot",
                    "uniqueName": "triage-system@service",
                },
                "Custom.ROBAnalysisState": "Pending",
            },
        )
        result = processor.process(payload)
        
        assert result["should_evaluate"] is False
    
    def test_normal_user_not_blocked(self, processor):
        """Normal user updates pass through"""
        payload = _make_payload(
            event_type="workitem.updated",
            fields={
                "System.ChangedBy": "brad.price@microsoft.com",
                "Custom.ROBAnalysisState": "Pending",
            },
        )
        result = processor.process(payload)
        
        assert result["should_evaluate"] is True


# =============================================================================
# 5. Terminal State Tests
# =============================================================================

class TestTerminalStates:
    """Test that terminal states are skipped"""
    
    def test_approved_skipped(self, processor):
        """Items in 'Approved' state are skipped"""
        payload = _make_payload(
            fields={
                "Custom.ROBAnalysisState": "Approved",
                "System.ChangedBy": "user@example.com",
            }
        )
        result = processor.process(payload)
        
        assert result["should_evaluate"] is False
        assert "terminal state" in result["skip_reason"].lower()
    
    def test_override_skipped(self, processor):
        """Items in 'Override' state are skipped"""
        payload = _make_payload(
            fields={
                "Custom.ROBAnalysisState": "Override",
                "System.ChangedBy": "user@example.com",
            }
        )
        result = processor.process(payload)
        
        assert result["should_evaluate"] is False
    
    def test_pending_not_skipped(self, processor):
        """Items in 'Pending' state are NOT skipped"""
        payload = _make_payload(
            fields={
                "Custom.ROBAnalysisState": "Pending",
                "System.ChangedBy": "user@example.com",
            }
        )
        result = processor.process(payload)
        
        assert result["should_evaluate"] is True
    
    def test_awaiting_approval_not_skipped(self, processor):
        """Items in 'Awaiting Approval' can be re-evaluated"""
        payload = _make_payload(
            fields={
                "Custom.ROBAnalysisState": "Awaiting Approval",
                "System.ChangedBy": "user@example.com",
            }
        )
        result = processor.process(payload)
        
        assert result["should_evaluate"] is True
    
    def test_no_state_field(self, processor):
        """Missing ROBAnalysisState is NOT terminal"""
        payload = _make_payload(
            fields={
                "System.Title": "No State",
                "System.ChangedBy": "user@example.com",
            }
        )
        result = processor.process(payload)
        
        assert result["should_evaluate"] is True


# =============================================================================
# 6. Meaningful Changes Tests
# =============================================================================

class TestMeaningfulChanges:
    """Test detection of meaningful vs. metadata-only updates"""
    
    def test_created_events_always_evaluate(self, processor):
        """Created events don't check for meaningful changes"""
        payload = _make_payload(event_type="workitem.created")
        result = processor.process(payload)
        assert result["should_evaluate"] is True
    
    def test_updated_with_unknown_changes(self, processor):
        """When changed fields can't be determined, evaluate (safe fallback)"""
        payload = _make_payload(
            event_type="workitem.updated",
            fields={
                "System.ChangedBy": "user@example.com",
                "Custom.ROBAnalysisState": "Pending",
            },
        )
        result = processor.process(payload)
        
        # Should evaluate because we can't determine what changed
        assert result["should_evaluate"] is True


# =============================================================================
# 7. Full Pipeline Tests
# =============================================================================

class TestFullPipeline:
    """End-to-end process() calls"""
    
    def test_new_item_evaluates(self, processor):
        """New work item in Pending state → should evaluate"""
        payload = _make_payload(
            event_type="workitem.created",
            fields={
                "System.Id": 100,
                "System.Title": "New Action",
                "Custom.ROBAnalysisState": "Pending",
                "System.ChangedBy": "creator@example.com",
            },
        )
        
        result = processor.process(payload)
        
        assert result["should_evaluate"] is True
        assert result["work_item_id"] == 12345
        assert result["event_type"] == "workitem.created"
    
    def test_result_contains_all_keys(self, processor):
        """Result dict has all expected keys"""
        payload = _make_payload()
        result = processor.process(payload)
        
        expected_keys = {
            "should_evaluate", "work_item_id", "event_type",
            "skip_reason", "fields", "revision", "received_at",
        }
        assert expected_keys.issubset(result.keys())
    
    def test_received_at_is_iso_timestamp(self, processor):
        """received_at is an ISO 8601 timestamp"""
        payload = _make_payload()
        result = processor.process(payload)
        
        # Should parse as datetime
        from datetime import datetime
        dt = datetime.fromisoformat(result["received_at"])
        assert dt is not None


# =============================================================================
# 8. HMAC Validation Tests
# =============================================================================

class TestHmacValidation:
    """Test webhook signature verification"""
    
    def test_no_secret_always_valid(self, processor):
        """Without shared secret, all payloads are valid"""
        assert processor.validate_signature(b"anything", None) is True
        assert processor.validate_signature(b"anything", "sha256=abc") is True
    
    def test_valid_signature(self, processor_with_secret):
        """Correct HMAC-SHA256 signature passes"""
        payload = b'{"eventType": "workitem.created"}'
        expected = hmac.new(
            b"test-secret-key", payload, hashlib.sha256
        ).hexdigest()
        
        assert processor_with_secret.validate_signature(
            payload, f"sha256={expected}"
        ) is True
    
    def test_invalid_signature(self, processor_with_secret):
        """Wrong signature fails"""
        payload = b'{"eventType": "workitem.created"}'
        
        assert processor_with_secret.validate_signature(
            payload, "sha256=invalid-hash"
        ) is False
    
    def test_missing_signature_with_secret(self, processor_with_secret):
        """Missing signature header fails when secret is configured"""
        assert processor_with_secret.validate_signature(
            b"data", None
        ) is False


# =============================================================================
# 9. Statistics Tests
# =============================================================================

class TestStatistics:
    """Test webhook processing counters"""
    
    def test_initial_stats(self, processor):
        """Fresh processor starts at zero"""
        stats = processor.get_stats()
        assert stats["processed"] == 0
        assert stats["skipped"] == 0
        assert stats["total"] == 0
    
    def test_processed_count(self, processor):
        """Successful evaluation increments processed counter"""
        payload = _make_payload()
        processor.process(payload)
        
        stats = processor.get_stats()
        assert stats["processed"] == 1
        assert stats["total"] == 1
    
    def test_skipped_count(self, processor):
        """Skipped evaluation increments skipped counter"""
        payload = _make_payload(event_type="workitem.deleted")
        processor.process(payload)
        
        stats = processor.get_stats()
        assert stats["skipped"] == 1
    
    def test_mixed_counts(self, processor):
        """Mix of processed and skipped"""
        # One that evaluates
        processor.process(_make_payload())
        # One that's skipped (bad event type)
        processor.process(_make_payload(event_type="build.completed"))
        # Another that evaluates
        processor.process(_make_payload(work_item_id=200))
        
        stats = processor.get_stats()
        assert stats["processed"] == 2
        assert stats["skipped"] == 1
        assert stats["total"] == 3
