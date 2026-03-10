"""
Phase 2 Unit Tests: ADO Client Adapter
========================================

Tests for the triage ADO adapter (triage/services/ado_client.py).
The adapter wraps AzureDevOpsClient — all auth is mocked via the
mock inner client. HTTP calls for new methods are also mocked.

Test Groups:
    1. Configuration:       TriageAdoConfig dual-org defaults
    2. URL Builders:        Read (production) vs Write (test) URLs
    3. get_work_item:       Single item fetch (200, 404, error)
    4. get_work_items_batch: Batch fetch (chunking, partial failures)
    5. update_work_item:    JSON Patch operations (200, 409, 400)
    6. add_comment:         Discussion comment posting
    7. query_triage_queue:  WIQL queries with filters
    8. set_analysis_state:  Convenience state setter
    9. get_field_definitions: Delegated to AzureDevOpsClient
    10. test_connection:    Delegated to AzureDevOpsClient
    11. get_work_item_link: Browser URL generation
    12. Headers:            Token reuse from inner client
    13. Singleton:          get_ado_client / reset_ado_client
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from typing import Dict, Any

from triage.services.ado_client import AdoClient, TriageAdoConfig


# =============================================================================
# Fixtures
# =============================================================================

class MockCredential:
    """Fake Azure credential that returns a fake token."""
    def get_token(self, scope):
        mock_token = MagicMock()
        mock_token.token = "fake-bearer-token-12345"
        return mock_token


@pytest.fixture
def mock_inner_client():
    """
    Create a mock AzureDevOpsClient to pass into AdoClient.

    This avoids triggering real authentication. The mock provides:
        - credential:  MockCredential (for token generation)
        - config:      With ADO_SCOPE for token calls
        - All methods:  MagicMock defaults
    """
    mock = MagicMock()
    mock.credential = MockCredential()
    mock.config = MagicMock()
    mock.config.ADO_SCOPE = "499b84ac-1321-427f-aa17-267ca6975798/.default"
    return mock


@pytest.fixture
def mock_ado_client(mock_inner_client):
    """
    Create an AdoClient adapter wrapping the mock inner client.

    No real auth happens — the mock credential returns fake tokens.
    """
    client = AdoClient(ado_client=mock_inner_client)
    return client


@pytest.fixture
def config():
    """Get the default triage ADO config."""
    return TriageAdoConfig()


# =============================================================================
# 1. Configuration Tests  (dual-org)
# =============================================================================

class TestTriageAdoConfig:
    """Test the dual-org configuration defaults."""

    def test_read_organization(self, config):
        """Production org for reads."""
        assert config.READ_ORGANIZATION == "unifiedactiontracker"

    def test_read_project(self, config):
        """Production project for reads."""
        assert config.READ_PROJECT == "Unified Action Tracker"

    def test_write_organization(self, config):
        """Test org for writes."""
        assert config.WRITE_ORGANIZATION == "unifiedactiontrackertest"

    def test_write_project(self, config):
        """Test project for writes."""
        assert config.WRITE_PROJECT == "Unified Action Tracker Test"

    def test_backward_compat_aliases(self, config):
        """ORGANIZATION/PROJECT/BASE_URL point to write org for compat."""
        assert config.ORGANIZATION == config.WRITE_ORGANIZATION
        assert config.PROJECT == config.WRITE_PROJECT
        assert config.BASE_URL == config.WRITE_BASE_URL

    def test_api_version(self, config):
        assert config.API_VERSION == "7.0"

    def test_work_item_type(self, config):
        assert config.WORK_ITEM_TYPE == "Actions"

    def test_ado_scope(self, config):
        assert "499b84ac" in config.ADO_SCOPE
        assert config.ADO_SCOPE.endswith("/.default")


# =============================================================================
# 2. URL Builder Tests  (read vs write separation)
# =============================================================================

class TestUrlBuilders:
    """Test URL construction — reads hit production, writes hit test."""

    def test_read_work_item_url_uses_production(self, mock_ado_client):
        url = mock_ado_client._read_work_item_url(12345)
        assert "workitems/12345" in url
        assert "unifiedactiontracker/" in url
        assert "Unified%20Action%20Tracker/" in url
        assert "api-version=7.0" in url
        # Must NOT contain "test" — this is the production org
        assert "unifiedactiontrackertest" not in url

    def test_read_batch_url_uses_production(self, mock_ado_client):
        url = mock_ado_client._read_batch_url([100, 200, 300])
        assert "ids=100,200,300" in url
        assert "$expand=All" in url
        assert "unifiedactiontracker/" in url
        assert "unifiedactiontrackertest" not in url

    def test_read_wiql_url_uses_production(self, mock_ado_client):
        url = mock_ado_client._read_wiql_url()
        assert "wiql" in url
        assert "unifiedactiontracker/" in url
        assert "unifiedactiontrackertest" not in url

    def test_write_work_item_url_uses_test(self, mock_ado_client):
        url = mock_ado_client._write_work_item_url(12345)
        assert "workitems/12345" in url
        assert "unifiedactiontrackertest" in url

    def test_write_comment_url_uses_test(self, mock_ado_client):
        url = mock_ado_client._write_comment_url(999)
        assert "workitems/999/comments" in url
        assert "7.0-preview.3" in url
        assert "unifiedactiontrackertest" in url

    def test_work_item_link_uses_production(self, mock_ado_client):
        link = mock_ado_client.get_work_item_link(42)
        assert "_workitems/edit/42" in link
        assert "dev.azure.com" in link
        assert "unifiedactiontracker/" in link
        # Link goes to production where real data lives
        assert "unifiedactiontrackertest" not in link


# =============================================================================
# 3. get_work_item Tests
# =============================================================================

class TestGetWorkItem:
    """Test single work item retrieval"""
    
    @patch("triage.services.ado_client.http_requests.get")
    def test_success(self, mock_get, mock_ado_client):
        """200 OK returns fields, id, rev"""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "id": 12345,
                "rev": 3,
                "fields": {
                    "System.Title": "Test Item",
                    "System.AreaPath": "UAT\\MCAPS",
                },
                "url": "https://example.com/api/12345",
            },
        )
        
        result = mock_ado_client.get_work_item(12345)
        
        assert result["success"] is True
        assert result["id"] == 12345
        assert result["rev"] == 3
        assert result["fields"]["System.Title"] == "Test Item"
    
    @patch("triage.services.ado_client.http_requests.get")
    def test_not_found(self, mock_get, mock_ado_client):
        """404 returns success=False with descriptive error"""
        mock_get.return_value = MagicMock(
            status_code=404,
            text="Not Found",
        )
        
        result = mock_ado_client.get_work_item(99999)
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    @patch("triage.services.ado_client.http_requests.get")
    def test_server_error(self, mock_get, mock_ado_client):
        """500 returns success=False"""
        mock_get.return_value = MagicMock(
            status_code=500,
            text="Internal Server Error",
        )
        
        result = mock_ado_client.get_work_item(12345)
        
        assert result["success"] is False
        assert "500" in result["error"]
    
    @patch("triage.services.ado_client.http_requests.get")
    def test_network_error(self, mock_get, mock_ado_client):
        """Network exception returns success=False"""
        mock_get.side_effect = ConnectionError("Network unreachable")
        
        result = mock_ado_client.get_work_item(12345)
        
        assert result["success"] is False
        assert "Network unreachable" in result["error"]


# =============================================================================
# 4. get_work_items_batch Tests
# =============================================================================

class TestGetWorkItemsBatch:
    """Test batch work item retrieval"""
    
    @patch("triage.services.ado_client.http_requests.get")
    def test_batch_success(self, mock_get, mock_ado_client):
        """Successful batch of 3 items"""
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "value": [
                    {"id": 1, "rev": 1, "fields": {"System.Title": "A"}, "url": ""},
                    {"id": 2, "rev": 2, "fields": {"System.Title": "B"}, "url": ""},
                    {"id": 3, "rev": 3, "fields": {"System.Title": "C"}, "url": ""},
                ]
            },
        )
        
        result = mock_ado_client.get_work_items_batch([1, 2, 3])
        
        assert result["success"] is True
        assert len(result["items"]) == 3
        assert result["failed_ids"] == []
    
    def test_empty_list(self, mock_ado_client):
        """Empty ID list returns empty results with no API call"""
        result = mock_ado_client.get_work_items_batch([])
        assert result["success"] is True
        assert result["items"] == []
    
    @patch("triage.services.ado_client.http_requests.get")
    def test_batch_all_fail(self, mock_get, mock_ado_client):
        """All items fail"""
        mock_get.return_value = MagicMock(
            status_code=500,
            text="Server Error",
        )
        
        result = mock_ado_client.get_work_items_batch([1, 2, 3])
        
        assert result["success"] is False
        assert len(result["failed_ids"]) == 3
    
    @patch("triage.services.ado_client.http_requests.get")
    def test_batch_chunking(self, mock_get, mock_ado_client):
        """More than 200 items triggers multiple requests"""
        # Create 250 IDs — should be 2 chunks (200 + 50)
        ids = list(range(1, 251))
        
        # First chunk succeeds with 200 items, second with 50
        def side_effect(url, headers=None):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if "ids=1," in url:
                # First chunk
                mock_resp.json = lambda: {
                    "value": [
                        {"id": i, "rev": 1, "fields": {}, "url": ""}
                        for i in range(1, 201)
                    ]
                }
            else:
                # Second chunk
                mock_resp.json = lambda: {
                    "value": [
                        {"id": i, "rev": 1, "fields": {}, "url": ""}
                        for i in range(201, 251)
                    ]
                }
            return mock_resp
        
        mock_get.side_effect = side_effect
        
        result = mock_ado_client.get_work_items_batch(ids)
        
        assert result["success"] is True
        assert len(result["items"]) == 250
        # Should have made 2 API calls
        assert mock_get.call_count == 2


# =============================================================================
# 5. update_work_item Tests
# =============================================================================

class TestUpdateWorkItem:
    """Test work item updates via JSON Patch"""
    
    def _make_change(self, field, new_value):
        """Create a simple FieldChange-like object"""
        class _Change:
            pass
        c = _Change()
        c.field = field
        c.new_value = new_value
        return c
    
    @patch("triage.services.ado_client.http_requests.patch")
    def test_update_success(self, mock_patch, mock_ado_client):
        """Successful field update"""
        mock_patch.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 100, "rev": 4},
        )
        
        changes = [
            self._make_change("System.AssignedTo", "user@example.com"),
            self._make_change("Custom.pTriageType", "AI"),
        ]
        
        result = mock_ado_client.update_work_item(100, changes)
        
        assert result["success"] is True
        assert result["id"] == 100
        assert result["rev"] == 4
        
        # Verify JSON Patch format
        call_args = mock_patch.call_args
        operations = call_args.kwargs.get("json") or call_args[1].get("json")
        assert len(operations) == 2
        assert operations[0]["op"] == "add"
        assert operations[0]["path"] == "/fields/System.AssignedTo"
        assert operations[0]["value"] == "user@example.com"
    
    @patch("triage.services.ado_client.http_requests.patch")
    def test_update_conflict(self, mock_patch, mock_ado_client):
        """409 Conflict sets conflict=True"""
        mock_patch.return_value = MagicMock(
            status_code=409,
            text="Version conflict",
        )
        
        changes = [self._make_change("System.Title", "New title")]
        result = mock_ado_client.update_work_item(100, changes, revision=3)
        
        assert result["success"] is False
        assert result["conflict"] is True
    
    @patch("triage.services.ado_client.http_requests.patch")
    def test_update_bad_request(self, mock_patch, mock_ado_client):
        """400 Bad Request returns error"""
        mock_patch.return_value = MagicMock(
            status_code=400,
            text="Invalid field: Fake.Field",
        )
        
        changes = [self._make_change("Fake.Field", "value")]
        result = mock_ado_client.update_work_item(100, changes)
        
        assert result["success"] is False
        assert "Bad request" in result["error"]
    
    def test_update_no_changes(self, mock_ado_client):
        """Empty changes list returns success with no API call"""
        result = mock_ado_client.update_work_item(100, [])
        assert result["success"] is True
        assert result["message"] == "No changes to apply"
    
    @patch("triage.services.ado_client.http_requests.patch")
    def test_field_path_prefix(self, mock_patch, mock_ado_client):
        """Fields already with /fields/ prefix are not double-prefixed"""
        mock_patch.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 100, "rev": 5},
        )
        
        changes = [self._make_change("/fields/System.Title", "Test")]
        mock_ado_client.update_work_item(100, changes)
        
        operations = mock_patch.call_args.kwargs.get("json") or mock_patch.call_args[1].get("json")
        # Should NOT be /fields//fields/System.Title
        assert operations[0]["path"] == "/fields/System.Title"


# =============================================================================
# 6. add_comment Tests
# =============================================================================

class TestAddComment:
    """Test discussion comment posting"""
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_comment_success(self, mock_post, mock_ado_client):
        """Successful comment post"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 42},
        )
        
        result = mock_ado_client.add_comment(
            100, "<p>@user Please provide details</p>"
        )
        
        assert result["success"] is True
        assert result["comment_id"] == 42
        
        # Verify request body
        call_args = mock_post.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        assert body["text"] == "<p>@user Please provide details</p>"
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_comment_201(self, mock_post, mock_ado_client):
        """201 Created is also accepted"""
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"id": 43},
        )
        
        result = mock_ado_client.add_comment(100, "<p>Note</p>")
        assert result["success"] is True
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_comment_failure(self, mock_post, mock_ado_client):
        """Failed comment returns error"""
        mock_post.return_value = MagicMock(
            status_code=403,
            text="Forbidden",
        )
        
        result = mock_ado_client.add_comment(100, "<p>Blocked</p>")
        assert result["success"] is False
        assert "403" in result["error"]


# =============================================================================
# 7. query_triage_queue Tests
# =============================================================================

class TestQueryTriageQueue:
    """Test WIQL-based triage queue queries"""
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_query_with_state(self, mock_post, mock_ado_client):
        """Query with state filter returns matching IDs."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "workItems": [
                    {"id": 10}, {"id": 20}, {"id": 30},
                ]
            },
        )

        result = mock_ado_client.query_triage_queue(state_filter="Pending")

        assert result["success"] is True
        assert result["work_item_ids"] == [10, 20, 30]
        assert result["count"] == 3

        # Verify WIQL includes Pending filter and targets PRODUCTION project
        call_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "Pending" in call_body["query"]
        assert "Unified Action Tracker" in call_body["query"]
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_query_default_states(self, mock_post, mock_ado_client):
        """Query without state filter uses default multi-state IN clause"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"workItems": [{"id": 1}]},
        )
        
        mock_ado_client.query_triage_queue()
        
        call_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "IN" in call_body["query"]
        assert "Pending" in call_body["query"]
        assert "Awaiting Approval" in call_body["query"]
        assert "Needs Info" in call_body["query"]
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_query_with_area_path(self, mock_post, mock_ado_client):
        """Query with area path adds UNDER clause"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"workItems": []},
        )
        
        mock_ado_client.query_triage_queue(area_path="UAT\\MCAPS")
        
        call_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "UNDER" in call_body["query"]
        assert "UAT\\MCAPS" in call_body["query"]
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_query_max_results(self, mock_post, mock_ado_client):
        """max_results limits returned IDs"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "workItems": [{"id": i} for i in range(1, 101)]
            },
        )
        
        result = mock_ado_client.query_triage_queue(max_results=5)
        
        assert result["count"] == 5
        assert len(result["work_item_ids"]) == 5
        assert result["total_available"] == 100
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_query_failure(self, mock_post, mock_ado_client):
        """WIQL failure returns error"""
        mock_post.return_value = MagicMock(
            status_code=400,
            text="Bad WIQL syntax",
        )
        
        result = mock_ado_client.query_triage_queue()
        
        assert result["success"] is False
        assert "WIQL" in result["error"]
    
    @patch("triage.services.ado_client.http_requests.post")
    def test_query_empty(self, mock_post, mock_ado_client):
        """Empty result set returns empty list"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"workItems": []},
        )
        
        result = mock_ado_client.query_triage_queue()
        
        assert result["success"] is True
        assert result["work_item_ids"] == []
        assert result["count"] == 0


# =============================================================================
# 8. set_analysis_state Tests
# =============================================================================

class TestSetAnalysisState:
    """Test the convenience state setter"""
    
    @patch("triage.services.ado_client.http_requests.patch")
    def test_set_state(self, mock_patch, mock_ado_client):
        """Sets Custom.ROBAnalysisState field"""
        mock_patch.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": 100, "rev": 6},
        )
        
        result = mock_ado_client.set_analysis_state(100, "Awaiting Approval")
        
        assert result["success"] is True
        
        # Verify the correct field is set
        operations = mock_patch.call_args.kwargs.get("json") or mock_patch.call_args[1].get("json")
        assert len(operations) == 1
        assert operations[0]["path"] == "/fields/Custom.ROBAnalysisState"
        assert operations[0]["value"] == "Awaiting Approval"


# =============================================================================
# 9. get_field_definitions Tests
# =============================================================================

class TestGetFieldDefinitions:
    """Test field metadata retrieval — delegated to AzureDevOpsClient."""

    def test_success(self, mock_ado_client, mock_inner_client):
        """Delegates to existing get_work_item_fields() and normalizes response."""
        mock_inner_client.get_work_item_fields.return_value = {
            "success": True,
            "fields": [
                {"referenceName": "System.Title", "name": "Title", "type": "string"},
                {"referenceName": "Custom.SolutionArea", "name": "Solution Area", "type": "string"},
            ],
            "work_item_type": {"name": "Action"},
        }

        result = mock_ado_client.get_field_definitions()

        assert result["success"] is True
        assert len(result["fields"]) == 2
        assert result["work_item_type"] == "Actions"
        mock_inner_client.get_work_item_fields.assert_called_once()

    def test_failure(self, mock_ado_client, mock_inner_client):
        """Failure from inner client is passed through."""
        mock_inner_client.get_work_item_fields.return_value = {
            "success": False,
            "error": "Connection failed",
        }

        result = mock_ado_client.get_field_definitions()

        assert result["success"] is False
        assert "failed" in result["error"].lower()


# =============================================================================
# 10. test_connection Tests
# =============================================================================

class TestTestConnection:
    """Test ADO connectivity — delegated to AzureDevOpsClient."""

    def test_connected(self, mock_ado_client, mock_inner_client):
        """Successful connection shows both read and write org info."""
        mock_inner_client.test_connection.return_value = {
            "success": True,
            "message": "Connected",
        }

        result = mock_ado_client.test_connection()

        assert result["success"] is True
        assert result["organization"] == "unifiedactiontrackertest"
        assert result["project"] == "Unified Action Tracker Test"
        assert result["read_organization"] == "unifiedactiontracker"
        assert result["read_project"] == "Unified Action Tracker"
        mock_inner_client.test_connection.assert_called_once()

    def test_disconnected(self, mock_ado_client, mock_inner_client):
        """Failed connection passes error through."""
        mock_inner_client.test_connection.return_value = {
            "success": False,
            "error": "Auth failed",
        }

        result = mock_ado_client.test_connection()

        assert result["success"] is False
        assert "failed" in result["error"].lower()


# =============================================================================
# 11. Headers Tests
# =============================================================================

class TestHeaders:
    """Test header generation"""
    
    def test_default_json_content_type(self, mock_ado_client):
        headers = mock_ado_client._headers()
        assert headers["Content-Type"] == "application/json"
        assert "Bearer" in headers["Authorization"]
    
    def test_json_patch_content_type(self, mock_ado_client):
        headers = mock_ado_client._headers("application/json-patch+json")
        assert headers["Content-Type"] == "application/json-patch+json"


# =============================================================================
# 12. Singleton Tests
# =============================================================================

class TestSingleton:
    """Test get_ado_client / reset_ado_client"""
    
    def test_reset_clears_instance(self):
        """reset_ado_client sets the singleton to None"""
        from triage.services.ado_client import reset_ado_client, _ado_client_instance
        import triage.services.ado_client as module
        
        reset_ado_client()
        assert module._ado_client_instance is None
