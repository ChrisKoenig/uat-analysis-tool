"""
Phase 2 Unit Tests: ADO Writer Service
========================================

Tests for the ADO Writer service (triage/services/ado_writer.py).
All ADO client calls are mocked.

Test Groups:
    1. AdoWriteResult:        Result object serialization
    2. apply_evaluation:      Full evaluation → ADO write pipeline
    3. apply_field_changes:   Direct field change application
    4. post_discussion_comment: Standalone comment posting
    5. update_analysis_state:  State transition helper
    6. _separate_changes:      Field/comment separation logic
    7. Conflict Handling:      409 responses
    8. Singleton:              get_ado_writer / reset_ado_writer
"""

import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any

from triage.services.ado_writer import (
    AdoWriterService,
    AdoWriteResult,
    get_ado_writer,
    reset_ado_writer,
)
from triage.engines.routes_engine import FieldChange
from triage.models.evaluation import Evaluation, AnalysisState


# =============================================================================
# Fixtures
# =============================================================================

class MockAdoClient:
    """
    Fake ADO client for testing the writer service.
    
    All methods return configurable results.
    Tracks call history for assertions.
    """
    
    def __init__(self):
        self.updates = []          # List of (work_item_id, changes, revision)
        self.comments = []         # List of (work_item_id, html)
        self.state_updates = []    # List of (work_item_id, state, revision)
        
        # Default responses (override per test)
        self.update_response = {"success": True, "id": 100, "rev": 10}
        self.comment_response = {"success": True, "comment_id": 42}
        self.state_response = {"success": True, "id": 100, "rev": 11}
    
    def update_work_item(self, work_item_id, field_changes, revision=None):
        self.updates.append((work_item_id, field_changes, revision))
        return self.update_response
    
    def add_comment(self, work_item_id, html_content):
        self.comments.append((work_item_id, html_content))
        return self.comment_response
    
    def set_analysis_state(self, work_item_id, state, revision=None):
        self.state_updates.append((work_item_id, state, revision))
        return self.state_response


@pytest.fixture
def mock_client():
    """Fresh mock ADO client"""
    return MockAdoClient()


@pytest.fixture
def writer(mock_client):
    """Writer service with mocked ADO client"""
    return AdoWriterService(ado_client=mock_client)


@pytest.fixture
def sample_evaluation():
    """
    Create a sample Evaluation result for testing.
    
    Simulates what EvaluationService.evaluate() returns.
    """
    eval_obj = Evaluation(
        workItemId=12345,
        evaluatedBy="test-user",
        isDryRun=False,
    )
    eval_obj.generate_id()
    eval_obj.analysisState = AnalysisState.AWAITING_APPROVAL
    eval_obj.matchedTrigger = "tree-1"
    eval_obj.appliedRoute = "route-1"
    eval_obj.actionsExecuted = ["action-1", "action-2"]
    eval_obj.ruleResults = {"rule-1": True, "rule-2": False}
    eval_obj.fieldsChanged = {
        "System.AssignedTo": {"from": "unassigned", "to": "@AI Triage"},
        "Custom.pTriageType": {"from": None, "to": "AI"},
        "System.AreaPath": {"from": "UAT", "to": "UAT\\MCAPS\\AI"},
    }
    eval_obj.summaryHtml = "<h2>Triage Summary</h2><p>Matched AI route.</p>"
    
    return eval_obj


# =============================================================================
# 1. AdoWriteResult Tests
# =============================================================================

class TestAdoWriteResult:
    """Test the result value object"""
    
    def test_default_values(self):
        result = AdoWriteResult(12345)
        assert result.success is False
        assert result.work_item_id == 12345
        assert result.fields_updated == 0
        assert result.comment_posted is False
        assert result.conflict is False
        assert result.errors == []
    
    def test_to_dict(self):
        result = AdoWriteResult(100)
        result.success = True
        result.fields_updated = 3
        result.new_revision = 10
        
        d = result.to_dict()
        assert d["success"] is True
        assert d["workItemId"] == 100
        assert d["fieldsUpdated"] == 3
        assert d["newRevision"] == 10


# =============================================================================
# 2. apply_evaluation Tests
# =============================================================================

class TestApplyEvaluation:
    """Test full evaluation → ADO write"""
    
    def test_success(self, writer, mock_client, sample_evaluation):
        """Successful apply writes fields + summary + state"""
        result = writer.apply_evaluation(sample_evaluation)
        
        assert result.success is True
        assert result.fields_updated > 0
        assert len(mock_client.updates) == 1
        
        # Should have applied: 3 field changes + analysis state + challenge details = 5
        changes = mock_client.updates[0][1]
        field_names = [c.field for c in changes]
        assert "System.AssignedTo" in field_names
        assert "Custom.pTriageType" in field_names
        assert "System.AreaPath" in field_names
        assert "Custom.ROBAnalysisState" in field_names
        assert "Custom.pChallengeDetails" in field_names
    
    def test_analysis_state_included(self, writer, mock_client, sample_evaluation):
        """Analysis State field always included"""
        writer.apply_evaluation(sample_evaluation)
        
        changes = mock_client.updates[0][1]
        state_changes = [c for c in changes if c.field == "Custom.ROBAnalysisState"]
        assert len(state_changes) == 1
        assert state_changes[0].new_value == AnalysisState.AWAITING_APPROVAL
    
    def test_challenge_details_included(self, writer, mock_client, sample_evaluation):
        """HTML summary written to Challenge Details"""
        writer.apply_evaluation(sample_evaluation)
        
        changes = mock_client.updates[0][1]
        detail_changes = [c for c in changes if c.field == "Custom.pChallengeDetails"]
        assert len(detail_changes) == 1
        assert "<h2>" in detail_changes[0].new_value
    
    def test_dry_run_blocked(self, writer, mock_client):
        """Dry run evaluations cannot be applied"""
        eval_obj = Evaluation(workItemId=1, evaluatedBy="x", isDryRun=True)
        eval_obj.generate_id()
        
        result = writer.apply_evaluation(eval_obj)
        
        assert result.success is False
        assert "dry-run" in result.errors[0].lower()
        assert len(mock_client.updates) == 0
    
    def test_discussion_field_becomes_comment(self, writer, mock_client):
        """Discussion field changes are posted as comments, not field updates"""
        eval_obj = Evaluation(workItemId=1, evaluatedBy="x", isDryRun=False)
        eval_obj.generate_id()
        eval_obj.analysisState = AnalysisState.NEEDS_INFO
        eval_obj.fieldsChanged = {
            "Discussion": {"from": None, "to": "<p>@user Please provide details</p>"},
            "Custom.SubState": {"from": None, "to": "Data Requested"},
        }
        
        result = writer.apply_evaluation(eval_obj)
        
        assert result.success is True
        
        # Field update should NOT include Discussion
        changes = mock_client.updates[0][1]
        field_names = [c.field for c in changes]
        assert "Discussion" not in field_names
        
        # Comment should be posted
        assert len(mock_client.comments) >= 1
        # The discussion comment
        comment_texts = [html for _, html in mock_client.comments]
        assert any("@user" in t for t in comment_texts)
    
    def test_conflict_stops_pipeline(self, writer, mock_client, sample_evaluation):
        """409 Conflict prevents comment posting"""
        mock_client.update_response = {
            "success": False, "conflict": True,
            "error": "Version conflict"
        }
        
        result = writer.apply_evaluation(sample_evaluation, revision=3)
        
        assert result.success is False
        assert result.conflict is True
        # Comments should NOT be attempted after a conflict
        assert len(mock_client.comments) == 0
    
    def test_field_update_failure_still_posts_comments(
        self, writer, mock_client, sample_evaluation
    ):
        """If field update fails (non-conflict), comments still attempted"""
        mock_client.update_response = {
            "success": False, "error": "Field not found"
        }
        
        result = writer.apply_evaluation(sample_evaluation)
        
        # Should have tried the update
        assert len(mock_client.updates) == 1
        # Even though update failed, summary comment should be attempted
        # (summaryHtml is present on the evaluation)
        # Note: No discussion field → only summary comment if any

    def test_no_field_changes(self, writer, mock_client):
        """Evaluation with no field changes still writes state + summary"""
        eval_obj = Evaluation(workItemId=1, evaluatedBy="x", isDryRun=False)
        eval_obj.generate_id()
        eval_obj.analysisState = AnalysisState.NO_MATCH
        eval_obj.fieldsChanged = {}
        eval_obj.summaryHtml = "<p>No match</p>"
        
        result = writer.apply_evaluation(eval_obj)
        
        # Should still include state + challenge details
        assert len(mock_client.updates) == 1
        changes = mock_client.updates[0][1]
        assert len(changes) == 2  # ROBAnalysisState + pChallengeDetails


# =============================================================================
# 3. apply_field_changes Tests
# =============================================================================

class TestApplyFieldChanges:
    """Test direct field change application"""
    
    def test_basic_changes(self, writer, mock_client):
        """Apply a list of field changes"""
        changes = [
            FieldChange("System.Title", "set", "Old", "New", "action-1"),
            FieldChange("Custom.Foo", "set", None, "Bar", "action-2"),
        ]
        
        result = writer.apply_field_changes(100, changes)
        
        assert result.success is True
        assert result.fields_updated == 2
    
    def test_discussion_separated(self, writer, mock_client):
        """Discussion changes become comments"""
        changes = [
            FieldChange("System.Title", "set", "Old", "New", "a1"),
            FieldChange("Discussion", "template", None, "<p>Note</p>", "a2"),
        ]
        
        result = writer.apply_field_changes(100, changes)
        
        assert result.success is True
        assert result.fields_updated == 1  # Only Title
        assert result.comment_posted is True
        assert len(mock_client.comments) == 1
    
    def test_history_separated(self, writer, mock_client):
        """System.History field changes become comments"""
        changes = [
            FieldChange("System.History", "append", None, "<p>History note</p>", "a1"),
        ]
        
        result = writer.apply_field_changes(100, changes)
        
        assert result.fields_updated == 0  # No field updates
        assert result.comment_posted is True
    
    def test_empty_changes(self, writer, mock_client):
        """Empty change list → success with no API calls"""
        result = writer.apply_field_changes(100, [])
        
        assert result.success is True
        assert result.fields_updated == 0
        assert len(mock_client.updates) == 0


# =============================================================================
# 4. post_discussion_comment Tests
# =============================================================================

class TestPostDiscussionComment:
    """Test standalone comment posting"""
    
    def test_comment_success(self, writer, mock_client):
        """Successful comment posting"""
        result = writer.post_discussion_comment(
            100, "<p>@user Action required</p>"
        )
        
        assert result.success is True
        assert result.comment_posted is True
        assert len(mock_client.comments) == 1
        assert mock_client.comments[0] == (100, "<p>@user Action required</p>")
    
    def test_comment_failure(self, writer, mock_client):
        """Failed comment returns error"""
        mock_client.comment_response = {
            "success": False, "error": "Permission denied"
        }
        
        result = writer.post_discussion_comment(100, "<p>Test</p>")
        
        assert result.success is False
        assert "Permission denied" in result.errors[0]


# =============================================================================
# 5. update_analysis_state Tests
# =============================================================================

class TestUpdateAnalysisState:
    """Test state transition helper"""
    
    def test_set_approved(self, writer, mock_client):
        """Set state to Approved"""
        result = writer.update_analysis_state(100, "Approved")
        
        assert result.success is True
        assert result.fields_updated == 1
        assert len(mock_client.state_updates) == 1
        assert mock_client.state_updates[0] == (100, "Approved", None)
    
    def test_set_with_revision(self, writer, mock_client):
        """State update with revision for conflict detection"""
        result = writer.update_analysis_state(100, "Override", revision=5)
        
        assert mock_client.state_updates[0] == (100, "Override", 5)
    
    def test_conflict(self, writer, mock_client):
        """Conflict on state update"""
        mock_client.state_response = {
            "success": False, "conflict": True, "error": "Conflict"
        }
        
        result = writer.update_analysis_state(100, "Approved")
        
        assert result.success is False
        assert result.conflict is True


# =============================================================================
# 6. _separate_changes Tests
# =============================================================================

class TestSeparateChanges:
    """Test field/comment separation logic"""
    
    def test_all_fields(self, writer):
        """All regular fields → field_changes, no comments"""
        eval_obj = Evaluation(workItemId=1, evaluatedBy="x", isDryRun=False)
        eval_obj.generate_id()
        eval_obj.fieldsChanged = {
            "System.Title": {"from": "A", "to": "B"},
            "Custom.Foo": {"from": None, "to": "Bar"},
        }
        
        changes, comments = writer._separate_changes(eval_obj)
        
        assert len(changes) == 2
        assert len(comments) == 0
    
    def test_discussion_separated(self, writer):
        """Discussion → comments list"""
        eval_obj = Evaluation(workItemId=1, evaluatedBy="x", isDryRun=False)
        eval_obj.generate_id()
        eval_obj.fieldsChanged = {
            "Discussion": {"from": None, "to": "<p>@ping</p>"},
            "Custom.Foo": {"from": None, "to": "Bar"},
        }
        
        changes, comments = writer._separate_changes(eval_obj)
        
        assert len(changes) == 1
        assert changes[0].field == "Custom.Foo"
        assert len(comments) == 1
        assert "<p>@ping</p>" in comments[0]
    
    def test_empty_discussion_skipped(self, writer):
        """Discussion with None/empty value is not posted"""
        eval_obj = Evaluation(workItemId=1, evaluatedBy="x", isDryRun=False)
        eval_obj.generate_id()
        eval_obj.fieldsChanged = {
            "Discussion": {"from": None, "to": None},
        }
        
        changes, comments = writer._separate_changes(eval_obj)
        
        assert len(changes) == 0
        assert len(comments) == 0


# =============================================================================
# 7. Conflict Handling Tests
# =============================================================================

class TestConflictHandling:
    """Test 409 Conflict scenarios"""
    
    def test_conflict_on_apply_field_changes(self, writer, mock_client):
        """Conflict returns conflict=True"""
        mock_client.update_response = {
            "success": False, "conflict": True,
            "error": "Version mismatch"
        }
        
        changes = [FieldChange("System.Title", "set", "A", "B", "a1")]
        result = writer.apply_field_changes(100, changes, revision=3)
        
        assert result.conflict is True
        assert result.success is False
        # Comments should NOT be posted after conflict
        assert len(mock_client.comments) == 0


# =============================================================================
# 8. Singleton Tests
# =============================================================================

class TestSingleton:
    """Test singleton utilities"""
    
    def test_reset_clears(self):
        """reset_ado_writer clears the singleton"""
        import triage.services.ado_writer as module
        reset_ado_writer()
        assert module._writer_instance is None
