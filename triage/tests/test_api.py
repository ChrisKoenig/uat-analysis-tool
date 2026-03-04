"""
Unit Tests - API Endpoints
============================

Tests for the FastAPI REST API using TestClient.
Tests endpoint routing, request validation, error responses,
and HTTP status codes without requiring a live Cosmos DB connection.

NOTE: These tests mock the CrudService to avoid Cosmos DB dependency.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from triage.api.routes import app


# =============================================================================
# Test Client
# =============================================================================

client = TestClient(app)


# =============================================================================
# Health Endpoint
# =============================================================================

class TestHealthEndpoint:
    """Tests for /health"""
    
    def test_health_endpoint_exists(self):
        """GET /health returns a response"""
        with patch("triage.api.routes.get_cosmos_config") as mock:
            mock.return_value.health_check.return_value = {
                "status": "healthy"
            }
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "triage-api"
            assert data["version"] == "1.0.0"
    
    def test_health_degraded_on_db_error(self):
        """Health reports degraded when DB is down"""
        with patch("triage.api.routes.get_cosmos_config") as mock:
            mock.side_effect = Exception("DB connection failed")
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "degraded"


# =============================================================================
# Rules CRUD Endpoints
# =============================================================================

class TestRulesAPI:
    """Tests for /api/v1/rules endpoints"""
    
    @patch("triage.api.routes.get_crud")
    def test_list_rules(self, mock_get_crud):
        """GET /api/v1/rules returns list of rules"""
        mock_crud = MagicMock()
        mock_crud.list.return_value = ([
            {"id": "rule-1", "name": "Test Rule", "status": "active"}
        ], None)
        mock_get_crud.return_value = mock_crud
        
        response = client.get("/api/v1/rules")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["items"][0]["id"] == "rule-1"
    
    @patch("triage.api.routes.get_crud")
    def test_list_rules_with_status_filter(self, mock_get_crud):
        """GET /api/v1/rules?status=active filters by status"""
        mock_crud = MagicMock()
        mock_crud.list.return_value = ([], None)
        mock_get_crud.return_value = mock_crud
        
        response = client.get("/api/v1/rules?status=active")
        assert response.status_code == 200
        mock_crud.list.assert_called_once_with("rule", status="active")
    
    @patch("triage.api.routes.get_crud")
    def test_get_rule(self, mock_get_crud):
        """GET /api/v1/rules/{id} returns a single rule"""
        mock_crud = MagicMock()
        mock_crud.get.return_value = {
            "id": "rule-1", "name": "Test", "status": "active"
        }
        mock_get_crud.return_value = mock_crud
        
        response = client.get("/api/v1/rules/rule-1")
        assert response.status_code == 200
        assert response.json()["id"] == "rule-1"
    
    @patch("triage.api.routes.get_crud")
    def test_get_rule_not_found(self, mock_get_crud):
        """GET /api/v1/rules/{id} returns 404 for missing rule"""
        mock_crud = MagicMock()
        mock_crud.get.return_value = None
        mock_get_crud.return_value = mock_crud
        
        response = client.get("/api/v1/rules/rule-999")
        assert response.status_code == 404
    
    @patch("triage.api.routes.get_crud")
    def test_create_rule(self, mock_get_crud):
        """POST /api/v1/rules creates a new rule"""
        mock_crud = MagicMock()
        mock_crud.create.return_value = {
            "id": "rule-1", "name": "New Rule", "status": "active"
        }
        mock_get_crud.return_value = mock_crud
        
        response = client.post("/api/v1/rules", json={
            "name": "New Rule",
            "field": "Custom.SolutionArea",
            "operator": "equals",
            "value": "AMEA"
        })
        assert response.status_code == 201
    
    def test_create_rule_missing_name(self):
        """POST /api/v1/rules with missing name returns 422"""
        response = client.post("/api/v1/rules", json={
            "field": "Custom.SolutionArea",
            "operator": "equals",
        })
        assert response.status_code == 422  # Pydantic validation error
    
    @patch("triage.api.routes.get_crud")
    def test_update_rule(self, mock_get_crud):
        """PUT /api/v1/rules/{id} updates a rule"""
        mock_crud = MagicMock()
        mock_crud.update.return_value = {
            "id": "rule-1", "name": "Updated", "version": 2
        }
        mock_get_crud.return_value = mock_crud
        
        response = client.put("/api/v1/rules/rule-1", json={
            "name": "Updated",
            "version": 1
        })
        assert response.status_code == 200
    
    def test_update_rule_missing_version(self):
        """PUT /api/v1/rules/{id} requires version for optimistic locking"""
        response = client.put("/api/v1/rules/rule-1", json={
            "name": "Updated"
        })
        assert response.status_code == 422  # version is required
    
    @patch("triage.api.routes.get_crud")
    def test_update_rule_conflict(self, mock_get_crud):
        """PUT /api/v1/rules/{id} returns 409 on version conflict"""
        from triage.services.crud_service import ConflictError
        mock_crud = MagicMock()
        mock_crud.update.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud
        
        response = client.put("/api/v1/rules/rule-1", json={
            "name": "Updated",
            "version": 1
        })
        assert response.status_code == 409
    
    @patch("triage.api.routes.get_crud")
    def test_delete_rule(self, mock_get_crud):
        """DELETE /api/v1/rules/{id} deletes a rule"""
        mock_crud = MagicMock()
        mock_get_crud.return_value = mock_crud
        
        response = client.delete("/api/v1/rules/rule-1")
        assert response.status_code == 200
        assert response.json()["hard"] is False  # Soft delete by default
    
    @patch("triage.api.routes.get_crud")
    def test_delete_rule_hard(self, mock_get_crud):
        """DELETE /api/v1/rules/{id}?hard=true permanently deletes"""
        mock_crud = MagicMock()
        mock_get_crud.return_value = mock_crud
        
        response = client.delete("/api/v1/rules/rule-1?hard=true")
        assert response.status_code == 200
        assert response.json()["hard"] is True
    
    @patch("triage.api.routes.get_crud")
    def test_copy_rule(self, mock_get_crud):
        """POST /api/v1/rules/{id}/copy clones a rule"""
        mock_crud = MagicMock()
        mock_crud.copy.return_value = {
            "id": "rule-2", "name": "Copy of Test", "status": "staged"
        }
        mock_get_crud.return_value = mock_crud
        
        response = client.post("/api/v1/rules/rule-1/copy", json={})
        assert response.status_code == 201
    
    @patch("triage.api.routes.get_crud")
    def test_update_rule_status(self, mock_get_crud):
        """PUT /api/v1/rules/{id}/status changes status"""
        mock_crud = MagicMock()
        mock_crud.set_status.return_value = {
            "id": "rule-1", "status": "disabled"
        }
        mock_get_crud.return_value = mock_crud
        
        response = client.put("/api/v1/rules/rule-1/status", json={
            "status": "disabled",
            "version": 1
        })
        assert response.status_code == 200
    
    @patch("triage.api.routes.get_crud")
    def test_get_rule_references(self, mock_get_crud):
        """GET /api/v1/rules/{id}/references returns cross-refs"""
        mock_crud = MagicMock()
        mock_crud.find_references.return_value = {
            "triggers": ["dt-10", "dt-20"]
        }
        mock_get_crud.return_value = mock_crud
        
        response = client.get("/api/v1/rules/rule-1/references")
        assert response.status_code == 200
        data = response.json()
        assert "triggers" in data["references"]


# =============================================================================
# Evaluation Endpoint
# =============================================================================

class TestEvaluationAPI:
    """Tests for /api/v1/evaluate endpoints — Updated for Phase 2 ADO integration"""
    
    @patch("triage.api.routes.get_ado")
    @patch("triage.api.routes.get_eval")
    def test_evaluate_returns_results(self, mock_get_eval, mock_get_ado):
        """POST /api/v1/evaluate returns evaluation results (Phase 2)"""
        # Mock the ADO client
        mock_ado = MagicMock()
        mock_ado.get_work_item.return_value = {
            "success": True,
            "id": 12345,
            "rev": 1,
            "fields": {"System.Title": "Test"},
        }
        mock_ado.get_work_item_link.return_value = "https://dev.azure.com/test/_workitems/edit/12345"
        mock_get_ado.return_value = mock_ado
        
        # Mock the evaluation service
        mock_eval = MagicMock()
        mock_evaluation = MagicMock()
        mock_evaluation.id = "eval-1"
        mock_evaluation.analysisState = "No Match"
        mock_evaluation.matchedTrigger = None
        mock_evaluation.appliedRoute = None
        mock_evaluation.actionsExecuted = []
        mock_evaluation.ruleResults = {}
        mock_evaluation.fieldsChanged = {}
        mock_evaluation.errors = []
        mock_evaluation.isDryRun = True
        mock_evaluation.summaryHtml = "<p>No match</p>"
        mock_eval.evaluate.return_value = mock_evaluation
        mock_get_eval.return_value = mock_eval
        
        response = client.post("/api/v1/evaluate", json={
            "workItemIds": [12345]
        })
        assert response.status_code == 200
        data = response.json()
        assert "evaluations" in data
        assert "count" in data
        assert data["count"] == 1
    
    @patch("triage.api.routes.get_ado")
    @patch("triage.api.routes.get_eval")
    def test_evaluate_test_endpoint(self, mock_get_eval, mock_get_ado):
        """POST /api/v1/evaluate/test forces dry run"""
        mock_ado = MagicMock()
        mock_ado.get_work_item.return_value = {
            "success": True, "id": 12345, "rev": 1,
            "fields": {"System.Title": "Test"},
        }
        mock_ado.get_work_item_link.return_value = "https://test"
        mock_get_ado.return_value = mock_ado
        
        mock_eval = MagicMock()
        mock_result = MagicMock()
        mock_result.id = "eval-2"
        mock_result.analysisState = "No Match"
        mock_result.matchedTrigger = None
        mock_result.appliedRoute = None
        mock_result.actionsExecuted = []
        mock_result.ruleResults = {}
        mock_result.fieldsChanged = {}
        mock_result.errors = []
        mock_result.isDryRun = True
        mock_result.summaryHtml = ""
        mock_eval.evaluate.return_value = mock_result
        mock_get_eval.return_value = mock_eval
        
        response = client.post("/api/v1/evaluate/test", json={
            "workItemIds": [12345],
            "dryRun": False
        })
        assert response.status_code == 200


# =============================================================================
# Audit Endpoint
# =============================================================================

class TestAuditAPI:
    """Tests for /api/v1/audit endpoints"""
    
    @patch("triage.api.routes.get_audit")
    def test_list_audit(self, mock_get_audit):
        """GET /api/v1/audit returns entries"""
        mock_audit = MagicMock()
        mock_audit.get_recent.return_value = [
            {"id": "audit-1", "action": "created"}
        ]
        mock_get_audit.return_value = mock_audit
        
        response = client.get("/api/v1/audit")
        assert response.status_code == 200
        assert response.json()["count"] == 1
    
    @patch("triage.api.routes.get_audit")
    def test_get_entity_audit(self, mock_get_audit):
        """GET /api/v1/audit/{type}/{id} returns entity history"""
        mock_audit = MagicMock()
        mock_audit.get_entity_history.return_value = []
        mock_get_audit.return_value = mock_audit
        
        response = client.get("/api/v1/audit/rule/rule-1")
        assert response.status_code == 200
        assert response.json()["entityType"] == "rule"


# =============================================================================
# Validation Endpoint
# =============================================================================

class TestValidationAPI:
    """Tests for /api/v1/validation endpoints"""
    
    @patch("triage.api.routes.get_crud")
    def test_validation_warnings(self, mock_get_crud):
        """GET /api/v1/validation/warnings returns warnings list"""
        mock_crud = MagicMock()
        # Return empty lists for all entity types
        mock_crud.list.return_value = ([], None)
        mock_get_crud.return_value = mock_crud
        
        response = client.get("/api/v1/validation/warnings")
        assert response.status_code == 200
        assert "warnings" in response.json()
    
    @patch("triage.api.routes.get_crud")
    def test_validation_references(self, mock_get_crud):
        """GET /api/v1/validation/references/{type}/{id} returns refs"""
        mock_crud = MagicMock()
        mock_crud.find_references.return_value = {}
        mock_get_crud.return_value = mock_crud
        
        response = client.get(
            "/api/v1/validation/references/rule/rule-1"
        )
        assert response.status_code == 200
        assert response.json()["entityType"] == "rule"
