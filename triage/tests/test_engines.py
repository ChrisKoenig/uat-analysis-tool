"""
Unit Tests - Engines
=====================

Tests for the three triage evaluation engines:
    - RulesEngine: All 16 operators, field resolution, edge cases
    - TreeEngine: Priority ordering, AND/OR/NOT, disabled rules, missing rules
    - RoutesEngine: All 5 operations, template variables, field changes
"""

import pytest
from typing import Dict, Any

from triage.engines.rules_engine import RulesEngine
from triage.engines.tree_engine import TreeEngine, MissingRuleError
from triage.engines.routes_engine import RoutesEngine, FieldChange
from triage.models.rule import Rule
from triage.models.action import Action
from triage.models.tree import DecisionTree
from triage.models.route import Route
from triage.models.analysis_result import AnalysisResult


# =============================================================================
# Test Fixtures - Shared Data
# =============================================================================

def make_rule(id: str, field: str, operator: str, value=None, status="active"):
    """Helper to create a Rule instance for testing"""
    return Rule(
        id=id,
        name=f"Test {id}",
        field=field,
        operator=operator,
        value=value,
        status=status
    )


def make_action(id: str, field: str, operation: str, value=None, status="active"):
    """Helper to create an Action instance for testing"""
    return Action(
        id=id,
        name=f"Test {id}",
        field=field,
        operation=operation,
        value=value,
        status=status
    )


def make_tree(id: str, priority: int, expression: Dict, onTrue: str, status="active"):
    """Helper to create a DecisionTree instance for testing"""
    return DecisionTree(
        id=id,
        name=f"Test {id}",
        priority=priority,
        expression=expression,
        onTrue=onTrue,
        status=status
    )


# Sample work item for testing
SAMPLE_WORK_ITEM: Dict[str, Any] = {
    "System.Id": 12345,
    "System.Title": "Test Action Item",
    "System.State": "New",
    "System.AreaPath": "UAT\\MCAPS\\AI",
    "System.CreatedBy": "user@microsoft.com",
    "System.AssignedTo": "",
    "Custom.SolutionArea": "AMEA",
    "Custom.MilestoneID": None,
    "Custom.Products": ["Azure", "M365"],
    "Custom.Priority": 2,
    "Custom.SourceURL": "https://example.com",
    "Custom.Notes": "",
}


# =============================================================================
# RulesEngine Tests
# =============================================================================

class TestRulesEngineOperators:
    """Tests for all 16 operator implementations"""
    
    def setup_method(self):
        self.engine = RulesEngine()
        self.wi = SAMPLE_WORK_ITEM.copy()
    
    # --- equals / notEquals ---
    
    def test_equals_string_match(self):
        """equals: exact string match (case-insensitive)"""
        rule = make_rule("r1", "Custom.SolutionArea", "equals", "AMEA")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_equals_string_case_insensitive(self):
        """equals: case-insensitive comparison"""
        rule = make_rule("r1", "Custom.SolutionArea", "equals", "amea")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_equals_string_no_match(self):
        """equals: string does not match"""
        rule = make_rule("r1", "Custom.SolutionArea", "equals", "EMEA")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_equals_numeric(self):
        """equals: numeric comparison"""
        rule = make_rule("r1", "Custom.Priority", "equals", 2)
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_equals_null_vs_null(self):
        """equals: None equals None"""
        rule = make_rule("r1", "Custom.MilestoneID", "equals", None)
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_not_equals(self):
        """notEquals: inverse of equals"""
        rule = make_rule("r1", "Custom.SolutionArea", "notEquals", "EMEA")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_not_equals_same_value(self):
        """notEquals: same value returns False"""
        rule = make_rule("r1", "Custom.SolutionArea", "notEquals", "AMEA")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    # --- in / notIn ---
    
    def test_in_single_value(self):
        """in: single value found in list"""
        rule = make_rule("r1", "Custom.SolutionArea", "in", ["AMEA", "EMEA"])
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_in_value_not_found(self):
        """in: value not in list"""
        rule = make_rule("r1", "Custom.SolutionArea", "in", ["EMEA", "APAC"])
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_in_case_insensitive(self):
        """in: case-insensitive comparison"""
        rule = make_rule("r1", "Custom.SolutionArea", "in", ["amea", "emea"])
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_in_list_field_overlap(self):
        """in: list field with list value (overlap check)"""
        rule = make_rule("r1", "Custom.Products", "in", ["Azure", "GCP"])
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_in_list_field_no_overlap(self):
        """in: list field with no overlap"""
        rule = make_rule("r1", "Custom.Products", "in", ["GCP", "AWS"])
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_not_in(self):
        """notIn: inverse of in"""
        rule = make_rule("r1", "Custom.SolutionArea", "notIn", ["EMEA", "APAC"])
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_in_null_field(self):
        """in: null field value returns False"""
        rule = make_rule("r1", "Custom.MilestoneID", "in", ["abc", "def"])
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    # --- contains / notContains ---
    
    def test_contains_substring(self):
        """contains: substring found"""
        rule = make_rule("r1", "System.Title", "contains", "Action")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_contains_case_insensitive(self):
        """contains: case-insensitive"""
        rule = make_rule("r1", "System.Title", "contains", "action")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_contains_not_found(self):
        """contains: substring not found"""
        rule = make_rule("r1", "System.Title", "contains", "xyz")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_contains_in_list(self):
        """contains: checks list elements"""
        rule = make_rule("r1", "Custom.Products", "contains", "Azure")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_not_contains(self):
        """notContains: inverse of contains"""
        rule = make_rule("r1", "System.Title", "notContains", "xyz")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    # --- startsWith ---
    
    def test_starts_with_match(self):
        """startsWith: prefix found"""
        rule = make_rule("r1", "System.Title", "startsWith", "Test")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_starts_with_no_match(self):
        """startsWith: prefix not found"""
        rule = make_rule("r1", "System.Title", "startsWith", "xyz")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_starts_with_case_insensitive(self):
        """startsWith: case-insensitive"""
        rule = make_rule("r1", "System.Title", "startsWith", "test")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    # --- under (hierarchical path) ---
    
    def test_under_exact_match(self):
        """under: exact path match"""
        rule = make_rule("r1", "System.AreaPath", "under", "UAT\\MCAPS\\AI")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_under_parent_match(self):
        """under: child is under parent"""
        rule = make_rule("r1", "System.AreaPath", "under", "UAT\\MCAPS")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_under_root_match(self):
        """under: deep child is under root"""
        rule = make_rule("r1", "System.AreaPath", "under", "UAT")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_under_different_path(self):
        """under: different path returns False"""
        rule = make_rule("r1", "System.AreaPath", "under", "UAT\\Other")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_under_forward_slash(self):
        """under: normalizes forward slashes"""
        rule = make_rule("r1", "System.AreaPath", "under", "UAT/MCAPS")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    # --- matches (regex) ---
    
    def test_matches_simple(self):
        """matches: simple regex"""
        rule = make_rule("r1", "System.Title", "matches", r"Test.*Item")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_matches_no_match(self):
        """matches: regex doesn't match"""
        rule = make_rule("r1", "System.Title", "matches", r"^xyz")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_matches_invalid_regex(self):
        """matches: invalid regex returns False (no crash)"""
        rule = make_rule("r1", "System.Title", "matches", r"[invalid")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    # --- isNull / isNotNull ---
    
    def test_is_null_none_value(self):
        """isNull: None field is null"""
        rule = make_rule("r1", "Custom.MilestoneID", "isNull")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_is_null_empty_string(self):
        """isNull: empty string is null"""
        rule = make_rule("r1", "Custom.Notes", "isNull")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_is_null_with_value(self):
        """isNull: non-null field returns False"""
        rule = make_rule("r1", "Custom.SolutionArea", "isNull")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_is_null_missing_field(self):
        """isNull: missing field is null"""
        rule = make_rule("r1", "NonExistent.Field", "isNull")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_is_not_null_with_value(self):
        """isNotNull: non-null field"""
        rule = make_rule("r1", "Custom.SolutionArea", "isNotNull")
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_is_not_null_none(self):
        """isNotNull: null field"""
        rule = make_rule("r1", "Custom.MilestoneID", "isNotNull")
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    # --- gt / lt / gte / lte ---
    
    def test_gt_numeric(self):
        """gt: 2 > 1"""
        rule = make_rule("r1", "Custom.Priority", "gt", 1)
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_gt_not_greater(self):
        """gt: 2 > 3 is False"""
        rule = make_rule("r1", "Custom.Priority", "gt", 3)
        assert self.engine.evaluate_rule(rule, self.wi) is False
    
    def test_lt_numeric(self):
        """lt: 2 < 3"""
        rule = make_rule("r1", "Custom.Priority", "lt", 3)
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_gte_equal(self):
        """gte: 2 >= 2"""
        rule = make_rule("r1", "Custom.Priority", "gte", 2)
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_lte_equal(self):
        """lte: 2 <= 2"""
        rule = make_rule("r1", "Custom.Priority", "lte", 2)
        assert self.engine.evaluate_rule(rule, self.wi) is True
    
    def test_gt_null_returns_false(self):
        """gt: null field returns False"""
        rule = make_rule("r1", "Custom.MilestoneID", "gt", 1)
        assert self.engine.evaluate_rule(rule, self.wi) is False


class TestRulesEngineFieldResolution:
    """Tests for field resolution (ADO + Analysis.*)"""
    
    def setup_method(self):
        self.engine = RulesEngine()
    
    def test_resolve_analysis_field(self):
        """Analysis.* fields resolve from AnalysisResult"""
        analysis = AnalysisResult(category="Feature Request")
        rule = make_rule("r1", "Analysis.Category", "equals", "Feature Request")
        assert self.engine.evaluate_rule(rule, {}, analysis) is True
    
    def test_resolve_analysis_field_no_analysis(self):
        """Analysis.* fields return None when no analysis provided"""
        rule = make_rule("r1", "Analysis.Category", "isNull")
        assert self.engine.evaluate_rule(rule, {}) is True
    
    def test_resolve_case_insensitive_field(self):
        """Field resolution is case-insensitive"""
        wi = {"custom.solutionarea": "AMEA"}
        rule = make_rule("r1", "Custom.SolutionArea", "equals", "AMEA")
        assert self.engine.evaluate_rule(rule, wi) is True


class TestRulesEngineEvaluateAll:
    """Tests for evaluate_all() batch processing"""
    
    def setup_method(self):
        self.engine = RulesEngine()
        self.wi = SAMPLE_WORK_ITEM.copy()
        
    def test_evaluate_all_basic(self):
        """evaluate_all returns results for active rules"""
        rules = [
            make_rule("r1", "Custom.SolutionArea", "equals", "AMEA"),
            make_rule("r2", "Custom.MilestoneID", "isNull"),
            make_rule("r3", "Custom.SolutionArea", "equals", "EMEA"),
        ]
        results, skipped = self.engine.evaluate_all(rules, self.wi)
        assert results["r1"] is True
        assert results["r2"] is True
        assert results["r3"] is False
        assert len(skipped) == 0
    
    def test_evaluate_all_skips_disabled(self):
        """evaluate_all skips disabled rules"""
        rules = [
            make_rule("r1", "Custom.SolutionArea", "equals", "AMEA"),
            make_rule("r2", "Custom.MilestoneID", "isNull", status="disabled"),
        ]
        results, skipped = self.engine.evaluate_all(rules, self.wi)
        assert "r1" in results
        assert "r2" not in results
        assert "r2" in skipped


# =============================================================================
# TreeEngine Tests
# =============================================================================

class TestTreeEngine:
    """Tests for the DecisionTree evaluation engine"""
    
    def setup_method(self):
        self.engine = TreeEngine()
    
    def test_single_tree_match(self):
        """Single tree with matching AND expression"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1", "r2"]}, "route-1")
        ]
        results = {"r1": True, "r2": True}
        
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched == "dt-10"
        assert route == "route-1"
        assert len(errors) == 0
    
    def test_single_tree_no_match(self):
        """Single tree with non-matching expression"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1", "r2"]}, "route-1")
        ]
        results = {"r1": True, "r2": False}
        
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched is None
        assert route is None
    
    def test_priority_ordering(self):
        """Higher priority (lower number) tree wins"""
        trees = [
            make_tree("dt-20", 20, {"and": ["r3", "r4"]}, "route-2"),
            make_tree("dt-10", 10, {"and": ["r1", "r2"]}, "route-1"),
        ]
        results = {"r1": True, "r2": True, "r3": True, "r4": True}
        
        matched, route, errors = self.engine.evaluate(trees, results)
        # Priority 10 wins over 20 even though dt-20 is first in list
        assert matched == "dt-10"
        assert route == "route-1"
    
    def test_first_match_wins(self):
        """First matching tree (by priority) wins"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1", "r2"]}, "route-1"),
            make_tree("dt-20", 20, {"and": ["r3", "r4"]}, "route-2"),
        ]
        results = {"r1": True, "r2": True, "r3": True, "r4": True}
        
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched == "dt-10"
    
    def test_or_expression(self):
        """OR expression: any True child wins"""
        trees = [
            make_tree("dt-10", 10, {"or": ["r1", "r2"]}, "route-1")
        ]
        results = {"r1": False, "r2": True}
        
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched == "dt-10"
    
    def test_not_expression(self):
        """NOT expression: inverts result"""
        trees = [
            make_tree("dt-10", 10, {"and": [{"not": "r1"}, "r2"]}, "route-1")
        ]
        results = {"r1": False, "r2": True}
        
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched == "dt-10"  # NOT False = True, AND True = True
    
    def test_nested_expression(self):
        """Nested AND/OR expression"""
        trees = [
            make_tree(
                "dt-10", 10,
                {"and": ["r1", {"or": ["r2", "r3"]}]},
                "route-1"
            )
        ]
        results = {"r1": True, "r2": False, "r3": True}
        
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched == "dt-10"
    
    def test_disabled_rule_in_and(self):
        """Disabled rule in AND expression → tree = False"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1", "r2"]}, "route-1")
        ]
        results = {"r1": True}
        skipped = ["r2"]  # r2 is disabled
        
        matched, route, errors = self.engine.evaluate(
            trees, results, skipped
        )
        assert matched is None  # r2 treated as False → AND fails
    
    def test_disabled_rule_in_or(self):
        """Disabled rule in OR expression → treated as False, other rules can satisfy"""
        trees = [
            make_tree("dt-10", 10, {"or": ["r1", "r2"]}, "route-1")
        ]
        results = {"r1": True}
        skipped = ["r2"]  # r2 is disabled → False, but r1 is True
        
        matched, route, errors = self.engine.evaluate(
            trees, results, skipped
        )
        assert matched == "dt-10"  # r1 satisfies the OR
    
    def test_missing_rule_error(self):
        """Missing rule (not in results, not skipped) → error"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1", "r999"]}, "route-1")
        ]
        results = {"r1": True}  # r999 not here
        
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched is None
        assert len(errors) > 0
        assert "r999" in errors[0]
    
    def test_disabled_tree_skipped(self):
        """Disabled trees are not evaluated"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1", "r2"]}, "route-1",
                       status="disabled"),
            make_tree("dt-20", 20, {"and": ["r3", "r4"]}, "route-2"),
        ]
        results = {"r1": True, "r2": True, "r3": True, "r4": True}
        
        matched, route, errors = self.engine.evaluate(trees, results)
        assert matched == "dt-20"  # dt-10 skipped because disabled
    
    def test_evaluation_trace(self):
        """get_evaluation_trace evaluates ALL trees"""
        trees = [
            make_tree("dt-10", 10, {"and": ["r1", "r2"]}, "route-1"),
            make_tree("dt-20", 20, {"and": ["r3", "r4"]}, "route-2"),
        ]
        results = {"r1": True, "r2": True, "r3": True, "r4": True}
        
        trace = self.engine.get_evaluation_trace(trees, results)
        assert len(trace) == 2
        assert trace[0]["treeId"] == "dt-10"
        assert trace[0]["isWinner"] is True
        assert trace[1]["isWinner"] is False


# =============================================================================
# RoutesEngine Tests
# =============================================================================

class TestRoutesEngine:
    """Tests for the Routes engine operation handlers"""
    
    def setup_method(self):
        self.engine = RoutesEngine()
        self.wi = SAMPLE_WORK_ITEM.copy()
    
    def test_set_operation(self):
        """'set' overwrites a field value"""
        route = Route(id="route-1", name="Test", actions=["a1"])
        actions = {
            "a1": make_action("a1", "System.AreaPath", "set", "UAT\\NewArea"),
        }
        
        changes, errors = self.engine.compute_changes(route, actions, self.wi)
        assert len(changes) == 1
        assert changes[0].field == "System.AreaPath"
        assert changes[0].new_value == "UAT\\NewArea"
        assert changes[0].old_value == "UAT\\MCAPS\\AI"
    
    def test_copy_operation(self):
        """'copy' copies value from source field"""
        route = Route(id="route-1", name="Test", actions=["a1"])
        actions = {
            "a1": make_action("a1", "System.AssignedTo", "copy", "System.CreatedBy"),
        }
        
        changes, errors = self.engine.compute_changes(route, actions, self.wi)
        assert len(changes) == 1
        assert changes[0].new_value == "user@microsoft.com"
    
    def test_append_operation(self):
        """'append' appends to existing value"""
        wi = self.wi.copy()
        wi["Custom.Notes"] = "Existing note"
        route = Route(id="route-1", name="Test", actions=["a1"])
        actions = {
            "a1": make_action("a1", "Custom.Notes", "append", "; New note"),
        }
        
        changes, errors = self.engine.compute_changes(route, actions, wi)
        assert len(changes) == 1
        assert changes[0].new_value == "Existing note\n; New note"
    
    def test_append_to_empty(self):
        """'append' to empty field sets value"""
        route = Route(id="route-1", name="Test", actions=["a1"])
        actions = {
            "a1": make_action("a1", "Custom.Notes", "append", "New note"),
        }
        
        changes, errors = self.engine.compute_changes(route, actions, self.wi)
        assert len(changes) == 1
        # Empty string is not None, so append uses newline separator
        assert "New note" in changes[0].new_value
    
    def test_set_computed_today(self):
        """'set_computed' with today() sets current date"""
        route = Route(id="route-1", name="Test", actions=["a1"])
        actions = {
            "a1": make_action("a1", "Custom.Date", "set_computed", "today()"),
        }
        
        changes, errors = self.engine.compute_changes(route, actions, self.wi)
        assert len(changes) == 1
        # Should be a date string
        assert "202" in changes[0].new_value  # Starts with year
    
    def test_template_operation(self):
        """'template' resolves variables"""
        route = Route(id="route-1", name="Test", actions=["a1"])
        actions = {
            "a1": make_action(
                "a1", "Discussion", "template",
                "{CreatedBy} - Please provide the Milestone ID for item {WorkItemId}"
            ),
        }
        
        changes, errors = self.engine.compute_changes(route, actions, self.wi)
        assert len(changes) == 1
        assert "user@microsoft.com" in changes[0].new_value
        assert "12345" in changes[0].new_value
    
    def test_multiple_actions_in_order(self):
        """Route executes actions in order"""
        route = Route(id="route-1", name="Test", actions=["a1", "a2"])
        actions = {
            "a1": make_action("a1", "System.AreaPath", "set", "UAT\\New"),
            "a2": make_action("a2", "Custom.SolutionArea", "set", "EMEA"),
        }
        
        changes, errors = self.engine.compute_changes(route, actions, self.wi)
        assert len(changes) == 2
        assert changes[0].action_id == "a1"
        assert changes[1].action_id == "a2"
    
    def test_missing_action_skipped(self):
        """Missing actions are skipped (not crash)"""
        route = Route(id="route-1", name="Test", actions=["a1", "a999"])
        actions = {
            "a1": make_action("a1", "System.AreaPath", "set", "UAT\\New"),
        }
        
        # Should not raise; missing action logged/skipped
        changes, errors = self.engine.compute_changes(route, actions, self.wi)
        assert len(changes) >= 1
        assert len(errors) >= 1  # Missing action reported
    
    def test_preview_changes(self):
        """preview_changes returns action descriptions for admin UI"""
        route = Route(id="route-1", name="Test", actions=["a1"])
        actions = {
            "a1": make_action("a1", "System.AreaPath", "set", "UAT\\New"),
        }
        
        preview = self.engine.preview_changes(route, actions)
        assert len(preview) == 1
        assert preview[0]["actionId"] == "a1"


class TestFieldChange:
    """Tests for the FieldChange data class"""
    
    def test_create_field_change(self):
        """FieldChange stores all fields"""
        fc = FieldChange(
            field="System.AreaPath",
            operation="set",
            old_value="Old",
            new_value="New",
            action_id="action-1"
        )
        assert fc.field == "System.AreaPath"
        assert fc.old_value == "Old"
        assert fc.new_value == "New"
        assert fc.action_id == "action-1"


# =============================================================================
# Integration-Style Tests (Engine Combinations)
# =============================================================================

class TestEngineIntegration:
    """Tests combining multiple engines in a mini pipeline"""
    
    def test_full_pipeline_match(self):
        """Rules → Trees → Routes: end-to-end match"""
        # Step 1: Evaluate rules
        rules_engine = RulesEngine()
        rules = [
            make_rule("r1", "Custom.MilestoneID", "isNull"),
            make_rule("r2", "Custom.SolutionArea", "equals", "AMEA"),
        ]
        rule_results, skipped = rules_engine.evaluate_all(
            rules, SAMPLE_WORK_ITEM
        )
        assert rule_results["r1"] is True
        assert rule_results["r2"] is True
        
        # Step 2: Walk trees
        tree_engine = TreeEngine()
        trees = [
            make_tree(
                "dt-10", 10,
                {"and": ["r1", "r2"]},
                "route-1"
            )
        ]
        matched, route_id, errors = tree_engine.evaluate(
            trees, rule_results, skipped
        )
        assert matched == "dt-10"
        assert route_id == "route-1"
        
        # Step 3: Compute changes
        routes_engine = RoutesEngine()
        route = Route(
            id="route-1", name="AI Triage",
            actions=["a1", "a2"]
        )
        actions = {
            "a1": make_action(
                "a1", "System.AreaPath", "set", "UAT\\AI"
            ),
            "a2": make_action(
                "a2", "Discussion", "template",
                "{CreatedBy} - Routed to AI team"
            ),
        }
        changes, errors = routes_engine.compute_changes(
            route, actions, SAMPLE_WORK_ITEM
        )
        assert len(changes) == 2
        assert changes[0].new_value == "UAT\\AI"
        assert "user@microsoft.com" in changes[1].new_value
    
    def test_full_pipeline_no_match(self):
        """Rules → Trees → Routes: no tree matches"""
        rules_engine = RulesEngine()
        rules = [
            make_rule("r1", "Custom.SolutionArea", "equals", "EMEA"),  # Won't match
        ]
        rule_results, skipped = rules_engine.evaluate_all(
            rules, SAMPLE_WORK_ITEM
        )
        assert rule_results["r1"] is False
        
        tree_engine = TreeEngine()
        trees = [
            make_tree("dt-10", 10, {"and": ["r1", "r1"]}, "route-1")
        ]
        matched, route_id, errors = tree_engine.evaluate(
            trees, rule_results, skipped
        )
        assert matched is None
        assert route_id is None
