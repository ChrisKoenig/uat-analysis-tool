"""
Phase 2 Unit Tests: API Endpoints (ADO Integration)
=====================================================

Tests for the new Phase 2 API endpoints added to routes.py:
    - POST /api/v1/webhook/workitem  (Webhook receiver)
    - GET  /api/v1/webhook/stats     (Webhook stats)
    - GET  /api/v1/ado/status        (ADO connection check)
    - GET  /api/v1/ado/fields        (Field definitions)
    - New schemas: TriageQueueResponse, ApplyChangesResponse, etc.

Uses httpx + TestClient from FastAPI.
ADO client is mocked — no real network calls.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """
    FastAPI TestClient for the triage API.
    
    The app is imported from triage.api.routes.
    We don't mock ADO here — individual tests mock what they need.
    """
    from triage.api.routes import app
    return TestClient(app)


# =============================================================================
# Schema Tests
# =============================================================================

class TestNewSchemas:
    """Test the new Pydantic schema models"""
    
    def test_triage_queue_response(self):
        from triage.api.schemas import TriageQueueResponse
        resp = TriageQueueResponse(
            workItemIds=[1, 2, 3], count=3, totalAvailable=10
        )
        assert resp.count == 3
        assert resp.totalAvailable == 10
    
    def test_apply_changes_request(self):
        from triage.api.schemas import ApplyChangesRequest
        req = ApplyChangesRequest(
            evaluationId="eval-1", workItemId=100, revision=5
        )
        assert req.evaluationId == "eval-1"
        assert req.revision == 5
    
    def test_apply_changes_response(self):
        from triage.api.schemas import ApplyChangesResponse
        resp = ApplyChangesResponse(
            success=True, workItemId=100, fieldsUpdated=3,
            commentPosted=True, newRevision=6
        )
        assert resp.fieldsUpdated == 3
        assert resp.commentPosted is True
    
    def test_webhook_response(self):
        from triage.api.schemas import WebhookResponse
        resp = WebhookResponse(
            received=True, workItemId=123,
            shouldEvaluate=False, skipReason="Terminal state"
        )
        assert resp.shouldEvaluate is False
    
    def test_ado_connection_status(self):
        from triage.api.schemas import AdoConnectionStatus
        status = AdoConnectionStatus(
            connected=True,
            organization="unifiedactiontrackertest",
            project="Unified Action Tracker Test",
        )
        assert status.connected is True


# =============================================================================
# Webhook Endpoint Tests
# =============================================================================

class TestWebhookEndpoint:
    """Test POST /api/v1/webhook/workitem"""
    
    def test_created_event(self, client):
        """Work item created webhook returns 200"""
        payload = {
            "subscriptionId": "sub-1",
            "notificationId": 1,
            "eventType": "workitem.created",
            "resource": {
                "id": 100,
                "rev": 1,
                "fields": {
                    "System.Title": "Test",
                    "Custom.ROBAnalysisState": "Pending",
                    "System.ChangedBy": "user@example.com",
                },
            },
        }
        
        # Mock the ADO client to prevent real API calls during evaluation
        with patch("triage.api.routes.get_ado") as mock_get_ado:
            mock_ado = MagicMock()
            mock_ado.get_work_item.return_value = {
                "success": True,
                "id": 100,
                "rev": 1,
                "fields": {"System.Title": "Test"},
            }
            mock_get_ado.return_value = mock_ado
            
            # Also mock the evaluation service to prevent Cosmos DB calls
            with patch("triage.api.routes.get_eval") as mock_get_eval:
                mock_eval = MagicMock()
                mock_eval_result = MagicMock()
                mock_eval_result.analysisState = "Pending"
                mock_eval.evaluate.return_value = mock_eval_result
                mock_get_eval.return_value = mock_eval
                
                response = client.post(
                    "/api/v1/webhook/workitem", json=payload
                )
        
        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True
        assert data["workItemId"] == 100
    
    def test_unsupported_event_type(self, client):
        """Unsupported event type returns 200 with skipReason"""
        payload = {
            "eventType": "build.completed",
            "resource": {"id": 1, "rev": 1},
        }
        
        response = client.post("/api/v1/webhook/workitem", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["shouldEvaluate"] is False
        assert data["skipReason"] is not None
    
    def test_terminal_state_skipped(self, client):
        """Work item in Approved state is skipped"""
        payload = {
            "eventType": "workitem.updated",
            "resource": {
                "id": 200,
                "rev": 5,
                "fields": {
                    "Custom.ROBAnalysisState": "Approved",
                    "System.ChangedBy": "user@example.com",
                },
            },
        }
        
        response = client.post("/api/v1/webhook/workitem", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["shouldEvaluate"] is False
        assert "terminal" in data["skipReason"].lower()


# =============================================================================
# Webhook Stats Endpoint Tests
# =============================================================================

class TestWebhookStats:
    """Test GET /api/v1/webhook/stats"""
    
    def test_stats_endpoint(self, client):
        """Stats endpoint returns counter data"""
        response = client.get("/api/v1/webhook/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert "skipped" in data
        assert "total" in data


# =============================================================================
# ADO Status Endpoint Tests
# =============================================================================

class TestAdoStatusEndpoint:
    """Test GET /api/v1/ado/status"""
    
    def test_connected(self, client):
        """Returns connected status when ADO is reachable"""
        with patch("triage.api.routes.get_ado") as mock_get_ado:
            mock_ado = MagicMock()
            mock_ado.test_connection.return_value = {
                "success": True,
                "organization": "unifiedactiontrackertest",
                "project": "Unified Action Tracker Test",
                "message": "Connected",
            }
            mock_get_ado.return_value = mock_ado
            
            response = client.get("/api/v1/ado/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["organization"] == "unifiedactiontrackertest"
    
    def test_disconnected(self, client):
        """Returns error when ADO connection fails"""
        with patch("triage.api.routes.get_ado") as mock_get_ado:
            mock_get_ado.side_effect = Exception("Auth failed")
            
            response = client.get("/api/v1/ado/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["error"] is not None


# =============================================================================
# Health Check (updated to include ADO)
# =============================================================================

class TestHealthCheck:
    """Verify health endpoint still works with new imports"""
    
    def test_health_returns_200(self, client):
        """Basic health check still works"""
        # Mock Cosmos to avoid real DB calls
        with patch("triage.api.routes.get_cosmos_config") as mock_cosmos:
            mock_config = MagicMock()
            mock_config.health_check.return_value = {"status": "healthy"}
            mock_cosmos.return_value = mock_config
            
            response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["service"] == "triage-api"


# =============================================================================
# Phase 4 Schema Tests
# =============================================================================

class TestPhase4Schemas:
    """Test the Phase 4 Pydantic schema models (queue details)"""

    def test_queue_item_summary_all_fields(self):
        """QueueItemSummary accepts all expected fields"""
        from triage.api.schemas import QueueItemSummary
        item = QueueItemSummary(
            id=12345,
            rev=3,
            title="Test item",
            state="Active",
            areaPath="Project\\Area",
            assignedTo="user@example.com",
            analysisState="Pending",
            workItemType="Bug",
            createdDate="2026-01-01T00:00:00Z",
            changedDate="2026-02-01T12:00:00Z",
            adoLink="https://dev.azure.com/org/_workitems/edit/12345",
        )
        assert item.id == 12345
        assert item.state == "Active"
        assert item.analysisState == "Pending"
        assert item.adoLink.endswith("12345")

    def test_queue_item_summary_optional_fields(self):
        """QueueItemSummary defaults to empty strings for optional fields"""
        from triage.api.schemas import QueueItemSummary
        item = QueueItemSummary(id=1, rev=1, title="Minimal")
        assert item.state == ""
        assert item.assignedTo == ""
        assert item.analysisState == ""

    def test_triage_queue_details_response(self):
        """TriageQueueDetailsResponse wraps items correctly"""
        from triage.api.schemas import TriageQueueDetailsResponse, QueueItemSummary
        items = [
            QueueItemSummary(id=1, rev=1, title="Item A"),
            QueueItemSummary(id=2, rev=2, title="Item B"),
        ]
        resp = TriageQueueDetailsResponse(
            items=items, count=2, totalAvailable=10, failedIds=[3]
        )
        assert resp.count == 2
        assert resp.totalAvailable == 10
        assert resp.failedIds == [3]
        assert len(resp.items) == 2
        assert resp.items[0].title == "Item A"


# =============================================================================
# Queue Details Endpoint Tests
# =============================================================================

class TestQueueDetailsEndpoint:
    """
    Test GET /api/v1/ado/queue/details
    
    This endpoint combines queue query + batch work-item hydration
    into a single call, returning full item summaries.
    """

    def test_queue_details_success(self, client):
        """Returns hydrated items when ADO responds correctly"""
        mock_ado = MagicMock()
        mock_ado.get_work_item_link.side_effect = \
            lambda wid: f"https://ado.example.com/_workitems/edit/{wid}"

        # Mock query_triage_queue → returns IDs
        mock_ado.query_triage_queue.return_value = {
            "success": True,
            "work_item_ids": [100, 200],
            "count": 2,
            "total_available": 5,
        }

        # Mock get_work_items_batch → returns dict with "items" key
        mock_ado.get_work_items_batch.return_value = {
            "success": True,
            "items": [
                {
                    "id": 100,
                    "rev": 3,
                    "fields": {
                        "System.Title": "Fix auth bug",
                        "System.State": "Active",
                        "System.AreaPath": "Project\\Auth",
                        "System.AssignedTo": {"displayName": "Alice"},
                        "Custom.ROBAnalysisState": "Pending",
                        "System.WorkItemType": "Bug",
                        "System.CreatedDate": "2026-01-15T10:00:00Z",
                        "System.ChangedDate": "2026-02-01T15:30:00Z",
                    },
                },
                {
                    "id": 200,
                    "rev": 1,
                    "fields": {
                        "System.Title": "Update docs",
                        "System.State": "New",
                        "System.AreaPath": "Project\\Docs",
                        "System.WorkItemType": "Task",
                        "System.CreatedDate": "2026-02-01T08:00:00Z",
                        "System.ChangedDate": "2026-02-01T09:00:00Z",
                    },
                },
            ],
            "failed_ids": [],
        }

        with patch("triage.api.routes.get_ado", return_value=mock_ado):
            response = client.get("/api/v1/ado/queue/details")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["totalAvailable"] == 5
        assert len(data["items"]) == 2

        # First item fully hydrated
        item_a = data["items"][0]
        assert item_a["id"] == 100
        assert item_a["title"] == "Fix auth bug"
        assert item_a["state"] == "Active"
        assert item_a["assignedTo"] == "Alice"
        assert item_a["analysisState"] == "Pending"

        # Second item — no assignedTo defaults to empty string
        item_b = data["items"][1]
        assert item_b["id"] == 200
        assert item_b["assignedTo"] == ""

    def test_queue_details_empty_queue(self, client):
        """Returns empty list when no items match"""
        mock_ado = MagicMock()
        mock_ado.query_triage_queue.return_value = {
            "success": True,
            "work_item_ids": [],
            "count": 0,
            "total_available": 0,
        }

        with patch("triage.api.routes.get_ado", return_value=mock_ado):
            response = client.get("/api/v1/ado/queue/details?state=Pending")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["items"] == []

    def test_queue_details_ado_connection_failure(self, client):
        """Returns 503 when ADO client is unavailable"""
        with patch("triage.api.routes.get_ado", side_effect=Exception("ADO down")):
            response = client.get("/api/v1/ado/queue/details")

        assert response.status_code == 503
        assert "ADO" in response.json()["detail"]

    def test_queue_details_query_failure(self, client):
        """Returns 502 when ADO query fails"""
        mock_ado = MagicMock()
        mock_ado.query_triage_queue.return_value = {
            "success": False,
            "error": "WIQL parse error",
        }

        with patch("triage.api.routes.get_ado", return_value=mock_ado):
            response = client.get("/api/v1/ado/queue/details")

        assert response.status_code == 502
        assert "WIQL" in response.json()["detail"]

    def test_queue_details_passes_filters(self, client):
        """Filters are forwarded to the ADO query"""
        mock_ado = MagicMock()
        mock_ado.query_triage_queue.return_value = {
            "success": True,
            "work_item_ids": [],
            "count": 0,
        }

        with patch("triage.api.routes.get_ado", return_value=mock_ado):
            response = client.get(
                "/api/v1/ado/queue/details"
                "?state=Pending&area_path=Proj%5CAuth&max_results=10"
            )

        assert response.status_code == 200
        mock_ado.query_triage_queue.assert_called_once_with(
            state_filter="Pending",
            area_path="Proj\\Auth",
            max_results=10,
        )

    def test_queue_details_partial_batch_failure(self, client):
        """Handles work items that fail to hydrate"""
        mock_ado = MagicMock()
        mock_ado.get_work_item_link.side_effect = \
            lambda wid: f"https://ado.example.com/_workitems/edit/{wid}"
        mock_ado.query_triage_queue.return_value = {
            "success": True,
            "work_item_ids": [100, 200, 300],
            "count": 3,
            "total_available": 3,
        }
        # Only 2 of 3 items returned; 300 in failed_ids
        mock_ado.get_work_items_batch.return_value = {
            "success": True,
            "items": [
                {
                    "id": 100, "rev": 1,
                    "fields": {"System.Title": "A"},
                },
                {
                    "id": 200, "rev": 1,
                    "fields": {"System.Title": "B"},
                },
            ],
            "failed_ids": [300],
        }

        with patch("triage.api.routes.get_ado", return_value=mock_ado):
            response = client.get("/api/v1/ado/queue/details")

        assert response.status_code == 200
        data = response.json()
        # Should have 2 hydrated items
        assert len(data["items"]) == 2
        # failedIds should contain the missing ID
        assert 300 in data["failedIds"]
