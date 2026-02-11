"""
Unit Tests — Phase 5: Test Mode & Hardening
=============================================

Tests for all Phase 5 features:

1. **Staged Entity Filtering** — include_staged flag on engines
2. **Optimistic Locking** — version required on update, version
   conflict returns 409, version on delete and status
3. **Pre-Delete Reference Check** — cannot delete an entity that
   is still referenced by other entities
4. **Dry-Run Hardening** — dry-run evals stored, apply guard
   blocks committing dry-run results
5. **Broken Reference Validation** — warnings for trees/routes
   that reference non-existent rules/actions/routes
6. **Disabled Rule Warnings** — evaluation surfaces which
   disabled rules are referenced by active trees
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from triage.api.routes import app
from triage.engines.rules_engine import RulesEngine
from triage.engines.tree_engine import TreeEngine
from triage.models.rule import Rule
from triage.models.tree import DecisionTree
from triage.services.crud_service import ConflictError


# =============================================================================
# TestClient
# =============================================================================

client = TestClient(app)


# =============================================================================
# Helpers
# =============================================================================

def make_rule(id, field="Custom.SolutionArea", operator="equals",
              value="AMEA", status="active"):
    """Create a Rule instance for testing"""
    return Rule(
        id=id, name=f"Test {id}", field=field,
        operator=operator, value=value, status=status,
    )


def make_tree(id, priority, expression, onTrue, status="active"):
    """Create a DecisionTree instance for testing"""
    return DecisionTree(
        id=id, name=f"Test {id}", priority=priority,
        expression=expression, onTrue=onTrue, status=status,
    )


SAMPLE_WI = {
    "System.Id": 12345,
    "System.Title": "Test Item",
    "System.State": "New",
    "Custom.SolutionArea": "AMEA",
    "Custom.MilestoneID": None,
}


# =============================================================================
# 1. Staged Entity Filtering – RulesEngine
# =============================================================================

class TestRulesEngineStagedFiltering:
    """include_staged parameter on RulesEngine.evaluate_all()"""

    def setup_method(self):
        self.engine = RulesEngine()
        self.wi = SAMPLE_WI.copy()

    def test_staged_rules_skipped_by_default(self):
        """Staged rules are excluded when include_staged=False (default)"""
        rules = [
            make_rule("r1", status="active"),
            make_rule("r2", status="staged"),
        ]
        results, skipped = self.engine.evaluate_all(rules, self.wi)
        assert "r1" in results
        assert "r2" not in results
        assert "r2" in skipped

    def test_staged_rules_included_when_flag_set(self):
        """Staged rules participate when include_staged=True"""
        rules = [
            make_rule("r1", status="active"),
            make_rule("r2", status="staged"),
        ]
        results, skipped = self.engine.evaluate_all(
            rules, self.wi, include_staged=True
        )
        assert "r1" in results
        assert "r2" in results
        assert len(skipped) == 0

    def test_disabled_rules_excluded_even_with_staged_flag(self):
        """Disabled rules remain excluded even when include_staged=True"""
        rules = [
            make_rule("r1", status="active"),
            make_rule("r2", status="staged"),
            make_rule("r3", status="disabled"),
        ]
        results, skipped = self.engine.evaluate_all(
            rules, self.wi, include_staged=True
        )
        assert "r1" in results
        assert "r2" in results
        assert "r3" not in results
        assert "r3" in skipped


# =============================================================================
# 2. Staged Entity Filtering – TreeEngine
# =============================================================================

class TestTreeEngineStagedFiltering:
    """include_staged parameter on TreeEngine.evaluate()"""

    def setup_method(self):
        self.engine = TreeEngine()

    def test_staged_trees_skipped_by_default(self):
        """Staged trees are not evaluated when include_staged=False"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1"]}, "route-1", status="staged"),
            make_tree("dt-20", 20, {"and": ["r1"]}, "route-2", status="active"),
        ]
        results = {"r1": True}
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched == "dt-20"
        assert route == "route-2"

    def test_staged_trees_included_when_flag_set(self):
        """Staged trees participate when include_staged=True"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1"]}, "route-1", status="staged"),
            make_tree("dt-20", 20, {"and": ["r1"]}, "route-2", status="active"),
        ]
        results = {"r1": True}
        matched, route, errors = self.engine.evaluate(
            trees, results, include_staged=True
        )
        # dt-10 has higher priority (lower number) and should win
        assert matched == "dt-10"
        assert route == "route-1"

    def test_disabled_trees_excluded_even_with_staged_flag(self):
        """Disabled trees stay excluded even under include_staged=True"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1"]}, "route-1", status="disabled"),
            make_tree("dt-20", 20, {"and": ["r1"]}, "route-2", status="active"),
        ]
        results = {"r1": True}
        matched, route, errors = self.engine.evaluate(
            trees, results, include_staged=True
        )
        assert matched == "dt-20"


# =============================================================================
# 3. Optimistic Locking — API Layer
# =============================================================================

class TestOptimisticLocking:
    """Version enforcement on update, delete, and status changes"""

    def test_update_rule_requires_version(self):
        """PUT /rules/{id} without version returns 422"""
        response = client.put("/api/v1/rules/rule-1", json={
            "name": "Updated"
        })
        assert response.status_code == 422

    @patch("triage.api.routes.get_crud")
    def test_update_rule_version_conflict(self, mock_get_crud):
        """PUT /rules/{id} returns 409 on stale version"""
        mock_crud = MagicMock()
        mock_crud.update.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/rules/rule-1", json={
            "name": "Updated", "version": 1
        })
        assert response.status_code == 409
        assert "Version mismatch" in response.json()["detail"]

    def test_status_update_requires_version(self):
        """PUT /rules/{id}/status without version returns 422"""
        response = client.put("/api/v1/rules/rule-1/status", json={
            "status": "disabled"
        })
        assert response.status_code == 422

    @patch("triage.api.routes.get_crud")
    def test_status_update_with_version(self, mock_get_crud):
        """PUT /rules/{id}/status with version succeeds"""
        mock_crud = MagicMock()
        mock_crud.set_status.return_value = {
            "id": "rule-1", "status": "disabled", "version": 2
        }
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/rules/rule-1/status", json={
            "status": "disabled", "version": 1
        })
        assert response.status_code == 200

    @patch("triage.api.routes.get_crud")
    def test_status_update_conflict(self, mock_get_crud):
        """PUT /rules/{id}/status returns 409 on version conflict"""
        mock_crud = MagicMock()
        mock_crud.set_status.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/rules/rule-1/status", json={
            "status": "disabled", "version": 1
        })
        assert response.status_code == 409

    @patch("triage.api.routes.get_crud")
    def test_delete_with_version_conflict(self, mock_get_crud):
        """DELETE /rules/{id}?version=1 returns 409 on conflict"""
        mock_crud = MagicMock()
        mock_crud.delete.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/rules/rule-1?version=1")
        assert response.status_code == 409

    @patch("triage.api.routes.get_crud")
    def test_delete_passes_version_to_crud(self, mock_get_crud):
        """DELETE /rules/{id}?version=5 forwards version to crud.delete()"""
        mock_crud = MagicMock()
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/rules/rule-1?version=5")
        assert response.status_code == 200
        mock_crud.delete.assert_called_once_with(
            "rule", "rule-1",
            actor="api-user", hard_delete=False, version=5
        )


# =============================================================================
# 4. Pre-Delete Reference Check
# =============================================================================

class TestPreDeleteReferenceCheck:
    """Deleting entities that are still referenced returns 400"""

    @patch("triage.api.routes.get_crud")
    def test_delete_referenced_rule_blocked(self, mock_get_crud):
        """Cannot delete a rule that is still used by a tree"""
        mock_crud = MagicMock()
        mock_crud.delete.side_effect = ValueError(
            "Cannot delete rule 'rule-1': still referenced by tree(s): dt-10"
        )
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/rules/rule-1")
        assert response.status_code == 400
        assert "still referenced" in response.json()["detail"]

    @patch("triage.api.routes.get_crud")
    def test_delete_referenced_action_blocked(self, mock_get_crud):
        """Cannot delete an action that is still used by a route"""
        mock_crud = MagicMock()
        mock_crud.delete.side_effect = ValueError(
            "Cannot delete action 'action-1': still referenced by route(s): route-5"
        )
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/actions/action-1")
        assert response.status_code == 400
        assert "still referenced" in response.json()["detail"]

    @patch("triage.api.routes.get_crud")
    def test_delete_referenced_route_blocked(self, mock_get_crud):
        """Cannot delete a route that is still used by a tree's onTrue"""
        mock_crud = MagicMock()
        mock_crud.delete.side_effect = ValueError(
            "Cannot delete route 'route-1': still referenced by tree(s): dt-10"
        )
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/routes/route-1")
        assert response.status_code == 400
        assert "still referenced" in response.json()["detail"]

    @patch("triage.api.routes.get_crud")
    def test_delete_unreferenced_succeeds(self, mock_get_crud):
        """Deleting an entity with no references succeeds normally"""
        mock_crud = MagicMock()
        # No side_effect → no error → delete succeeds
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/rules/rule-1")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"


# =============================================================================
# 5. Dry-Run Apply Guard
# =============================================================================

class TestDryRunApplyGuard:
    """Dry-run evaluations cannot be applied to ADO"""

    @patch("triage.api.routes.get_ado")
    @patch("triage.api.routes.get_eval")
    def test_apply_dry_run_blocked(self, mock_get_eval, mock_get_ado):
        """POST /evaluate/apply returns 400 for dry-run evaluations"""
        mock_ado = MagicMock()
        mock_get_ado.return_value = mock_ado

        mock_eval = MagicMock()
        # Return a dry-run evaluation from history
        mock_eval.get_evaluation_history.return_value = [
            {"id": "eval-dry-1", "isDryRun": True, "fieldsChanged": []}
        ]
        mock_get_eval.return_value = mock_eval

        response = client.post("/api/v1/evaluate/apply", json={
            "workItemId": 12345,
            "evaluationId": "eval-dry-1",
        })
        assert response.status_code == 400
        assert "dry-run" in response.json()["detail"].lower()

    @patch("triage.api.routes.get_ado")
    @patch("triage.api.routes.get_eval")
    def test_apply_live_evaluation_allowed(self, mock_get_eval, mock_get_ado):
        """POST /evaluate/apply allows live (non-dry-run) evaluations"""
        mock_ado = MagicMock()
        mock_ado.update_work_item.return_value = {"success": True, "id": 12345}
        mock_get_ado.return_value = mock_ado

        mock_eval = MagicMock()
        mock_eval.get_evaluation_history.return_value = [
            {
                "id": "eval-live-1",
                "isDryRun": False,
                "fieldsChanged": {
                    "Custom.SolutionArea": {
                        "from": "AMEA",
                        "to": "EMEA",
                    }
                },
            }
        ]
        mock_get_eval.return_value = mock_eval

        response = client.post("/api/v1/evaluate/apply", json={
            "workItemId": 12345,
            "evaluationId": "eval-live-1",
        })
        # Should proceed (either succeed or fail on ADO write, not 400)
        assert response.status_code != 400

    @patch("triage.api.routes.get_ado")
    @patch("triage.api.routes.get_eval")
    def test_apply_missing_evaluation_404(self, mock_get_eval, mock_get_ado):
        """POST /evaluate/apply returns 404 for non-existent evaluation"""
        mock_ado = MagicMock()
        mock_get_ado.return_value = mock_ado

        mock_eval = MagicMock()
        mock_eval.get_evaluation_history.return_value = []
        mock_get_eval.return_value = mock_eval

        response = client.post("/api/v1/evaluate/apply", json={
            "workItemId": 12345,
            "evaluationId": "eval-nope",
        })
        assert response.status_code == 404


# =============================================================================
# 6. Broken Reference Validation
# =============================================================================

class TestBrokenReferenceValidation:
    """GET /validation/warnings surfaces broken references"""

    @patch("triage.api.routes.get_crud")
    def test_tree_references_missing_rule(self, mock_get_crud):
        """Trees referencing non-existent rules produce broken_reference warnings"""
        mock_crud = MagicMock()

        # Tree dt-10 references rule "r999" which doesn't exist
        tree_doc = {
            "id": "dt-10", "name": "Test Tree", "status": "active",
            "priority": 10, "onTrue": "route-1",
            "expression": {"and": ["r1", "r999"]},
        }

        rule_doc = {
            "id": "r1", "name": "Rule 1", "status": "active",
            "field": "Custom.SolutionArea", "operator": "equals", "value": "AMEA",
        }

        route_doc = {
            "id": "route-1", "name": "Route 1", "status": "active",
            "actions": [],
        }

        action_doc = {
            "id": "action-1", "name": "Action 1", "status": "active",
        }

        def list_entities(entity_type, **kwargs):
            if entity_type == "rule":
                return ([rule_doc], None)
            elif entity_type == "tree":
                return ([tree_doc], None)
            elif entity_type == "route":
                return ([route_doc], None)
            elif entity_type == "action":
                return ([action_doc], None)
            return ([], None)

        mock_crud.list.side_effect = list_entities
        mock_get_crud.return_value = mock_crud

        response = client.get("/api/v1/validation/warnings")
        assert response.status_code == 200
        warnings = response.json()["warnings"]
        broken_refs = [w for w in warnings if w.get("type") == "broken_reference"]
        assert len(broken_refs) >= 1
        # The broken ref should mention r999
        ref_texts = " ".join(str(w) for w in broken_refs)
        assert "r999" in ref_texts

    @patch("triage.api.routes.get_crud")
    def test_route_references_missing_action(self, mock_get_crud):
        """Routes referencing non-existent actions produce broken_reference warnings"""
        mock_crud = MagicMock()

        route_doc = {
            "id": "route-1", "name": "Test Route", "status": "active",
            "actions": ["action-1", "action-999"],  # action-999 doesn't exist
        }

        action_doc = {
            "id": "action-1", "name": "Action 1", "status": "active",
        }

        rule_doc = {
            "id": "r1", "name": "Rule 1", "status": "active",
            "field": "Custom.X", "operator": "equals", "value": "Y",
        }

        tree_doc = {
            "id": "dt-10", "name": "Tree 1", "status": "active",
            "expression": {"and": ["r1"]}, "priority": 10,
            "onTrue": "route-1",
        }

        def list_entities(entity_type, **kwargs):
            if entity_type == "rule":
                return ([rule_doc], None)
            elif entity_type == "tree":
                return ([tree_doc], None)
            elif entity_type == "route":
                return ([route_doc], None)
            elif entity_type == "action":
                return ([action_doc], None)
            return ([], None)

        mock_crud.list.side_effect = list_entities
        mock_get_crud.return_value = mock_crud

        response = client.get("/api/v1/validation/warnings")
        assert response.status_code == 200
        warnings = response.json()["warnings"]
        broken_refs = [w for w in warnings if w.get("type") == "broken_reference"]
        ref_texts = " ".join(str(w) for w in broken_refs)
        assert "action-999" in ref_texts

    @patch("triage.api.routes.get_crud")
    def test_tree_references_missing_route(self, mock_get_crud):
        """Trees referencing non-existent routes produce broken_reference warnings"""
        mock_crud = MagicMock()

        tree_doc = {
            "id": "dt-10", "name": "Test Tree", "status": "active",
            "expression": {"and": ["r1"]}, "priority": 10,
            "onTrue": "route-999",  # Doesn't exist
        }

        rule_doc = {
            "id": "r1", "name": "Rule 1", "status": "active",
            "field": "Custom.X", "operator": "equals", "value": "Y",
        }

        action_doc = {
            "id": "action-1", "name": "Action 1", "status": "active",
        }

        route_doc = {
            "id": "route-1", "name": "Route 1", "status": "active",
            "actions": [],
        }

        def list_entities(entity_type, **kwargs):
            if entity_type == "rule":
                return ([rule_doc], None)
            elif entity_type == "tree":
                return ([tree_doc], None)
            elif entity_type == "route":
                return ([route_doc], None)
            elif entity_type == "action":
                return ([action_doc], None)
            return ([], None)

        mock_crud.list.side_effect = list_entities
        mock_get_crud.return_value = mock_crud

        response = client.get("/api/v1/validation/warnings")
        assert response.status_code == 200
        warnings = response.json()["warnings"]
        broken_refs = [w for w in warnings if w.get("type") == "broken_reference"]
        ref_texts = " ".join(str(w) for w in broken_refs)
        assert "route-999" in ref_texts

    @patch("triage.api.routes.get_crud")
    def test_no_broken_references_clean(self, mock_get_crud):
        """No broken_reference warnings when all references are valid"""
        mock_crud = MagicMock()

        rule_doc = {
            "id": "r1", "name": "Rule 1", "status": "active",
            "field": "Custom.X", "operator": "equals", "value": "Y",
        }

        action_doc = {
            "id": "action-1", "name": "Action 1", "status": "active",
        }

        route_doc = {
            "id": "route-1", "name": "Route 1", "status": "active",
            "actions": ["action-1"],
        }

        tree_doc = {
            "id": "dt-10", "name": "Tree 1", "status": "active",
            "expression": {"and": ["r1"]}, "priority": 10,
            "onTrue": "route-1",
        }

        def list_entities(entity_type, **kwargs):
            if entity_type == "rule":
                return ([rule_doc], None)
            elif entity_type == "tree":
                return ([tree_doc], None)
            elif entity_type == "route":
                return ([route_doc], None)
            elif entity_type == "action":
                return ([action_doc], None)
            return ([], None)

        mock_crud.list.side_effect = list_entities
        mock_get_crud.return_value = mock_crud

        response = client.get("/api/v1/validation/warnings")
        assert response.status_code == 200
        warnings = response.json()["warnings"]
        broken_refs = [w for w in warnings if w.get("type") == "broken_reference"]
        assert len(broken_refs) == 0


# =============================================================================
# 7. Cross-Entity Optimistic Locking (Actions, Trees, Routes)
# =============================================================================

class TestOptimisticLockingAllEntities:
    """Version enforcement works for all four entity types"""

    @patch("triage.api.routes.get_crud")
    def test_update_action_version_conflict(self, mock_get_crud):
        """PUT /actions/{id} returns 409 on stale version"""
        mock_crud = MagicMock()
        mock_crud.update.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/actions/action-1", json={
            "name": "Updated", "version": 1
        })
        assert response.status_code == 409

    @patch("triage.api.routes.get_crud")
    def test_update_tree_version_conflict(self, mock_get_crud):
        """PUT /trees/{id} returns 409 on stale version"""
        mock_crud = MagicMock()
        mock_crud.update.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/trees/dt-10", json={
            "name": "Updated", "version": 1
        })
        assert response.status_code == 409

    @patch("triage.api.routes.get_crud")
    def test_update_route_version_conflict(self, mock_get_crud):
        """PUT /routes/{id} returns 409 on stale version"""
        mock_crud = MagicMock()
        mock_crud.update.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/routes/route-1", json={
            "name": "Updated", "version": 1
        })
        assert response.status_code == 409

    @patch("triage.api.routes.get_crud")
    def test_delete_action_version_conflict(self, mock_get_crud):
        """DELETE /actions/{id}?version=1 returns 409 on conflict"""
        mock_crud = MagicMock()
        mock_crud.delete.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/actions/action-1?version=1")
        assert response.status_code == 409

    @patch("triage.api.routes.get_crud")
    def test_status_action_conflict(self, mock_get_crud):
        """PUT /actions/{id}/status returns 409 on version conflict"""
        mock_crud = MagicMock()
        mock_crud.set_status.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/actions/action-1/status", json={
            "status": "disabled", "version": 1
        })
        assert response.status_code == 409

    @patch("triage.api.routes.get_crud")
    def test_status_tree_conflict(self, mock_get_crud):
        """PUT /trees/{id}/status returns 409 on version conflict"""
        mock_crud = MagicMock()
        mock_crud.set_status.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/trees/dt-10/status", json={
            "status": "disabled", "version": 1
        })
        assert response.status_code == 409

    @patch("triage.api.routes.get_crud")
    def test_status_route_conflict(self, mock_get_crud):
        """PUT /routes/{id}/status returns 409 on version conflict"""
        mock_crud = MagicMock()
        mock_crud.set_status.side_effect = ConflictError("Version mismatch")
        mock_get_crud.return_value = mock_crud

        response = client.put("/api/v1/routes/route-1/status", json={
            "status": "disabled", "version": 1
        })
        assert response.status_code == 409


# =============================================================================
# 8. Delete Without Version Still Works
# =============================================================================

class TestDeleteWithoutVersion:
    """Delete without version query param still succeeds (optional)"""

    @patch("triage.api.routes.get_crud")
    def test_delete_without_version(self, mock_get_crud):
        """DELETE /rules/{id} without version succeeds"""
        mock_crud = MagicMock()
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/rules/rule-1")
        assert response.status_code == 200
        mock_crud.delete.assert_called_once_with(
            "rule", "rule-1",
            actor="api-user", hard_delete=False, version=None
        )

    @patch("triage.api.routes.get_crud")
    def test_delete_hard_with_version(self, mock_get_crud):
        """DELETE /rules/{id}?hard=true&version=3 passes both params"""
        mock_crud = MagicMock()
        mock_get_crud.return_value = mock_crud

        response = client.delete("/api/v1/rules/rule-1?hard=true&version=3")
        assert response.status_code == 200
        mock_crud.delete.assert_called_once_with(
            "rule", "rule-1",
            actor="api-user", hard_delete=True, version=3
        )
