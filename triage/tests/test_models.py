"""
Unit Tests - Models
====================

Tests for all triage data models:
    - BaseEntity lifecycle (status, version, validation)
    - Rule model (operators, validation, display)
    - Action model (operations, validation, display)
    - Trigger model (expressions, referenced rules, validation)
    - Route model (action list management, validation)
"""

import pytest
from datetime import datetime

from triage.models.base import BaseEntity, EntityStatus, utc_now
from triage.models.rule import Rule, VALID_OPERATORS
from triage.models.action import Action, VALID_OPERATIONS
from triage.models.trigger import Trigger
from triage.models.route import Route
from triage.models.evaluation import Evaluation, AnalysisState
from triage.models.analysis_result import AnalysisResult
from triage.models.field_schema import FieldSchema
from triage.models.audit_entry import AuditEntry, AuditAction


# =============================================================================
# BaseEntity Tests
# =============================================================================

class TestBaseEntity:
    """Tests for the BaseEntity base class"""
    
    def test_create_default(self):
        """BaseEntity can be created with defaults"""
        entity = BaseEntity()
        assert entity.id == ""
        assert entity.name == ""
        assert entity.status == EntityStatus.ACTIVE
        assert entity.version == 1
        assert entity.createdDate != ""
    
    def test_create_with_fields(self):
        """BaseEntity can be created with all fields"""
        entity = BaseEntity(
            id="test-1",
            name="Test Entity",
            description="A test",
            status="active",
            version=1,
            createdBy="user@test.com"
        )
        assert entity.id == "test-1"
        assert entity.name == "Test Entity"
        assert entity.createdBy == "user@test.com"
    
    def test_to_dict(self):
        """to_dict() serializes all fields"""
        entity = BaseEntity(id="test-1", name="Test")
        d = entity.to_dict()
        assert d["id"] == "test-1"
        assert d["name"] == "Test"
        assert "status" in d
        assert "version" in d
        assert "createdDate" in d
    
    def test_from_dict(self):
        """from_dict() deserializes correctly"""
        data = {
            "id": "test-1",
            "name": "Test",
            "status": "active",
            "version": 2,
            "createdBy": "admin",
            "createdDate": "2026-01-01T00:00:00Z",
            "modifiedBy": "",
            "modifiedDate": "2026-01-01T00:00:00Z",
            "description": "",
        }
        entity = BaseEntity.from_dict(data)
        assert entity.id == "test-1"
        assert entity.version == 2
    
    def test_from_dict_ignores_unknown_fields(self):
        """from_dict() ignores Cosmos DB system fields"""
        data = {
            "id": "test-1",
            "name": "Test",
            "_rid": "abc123",
            "_self": "dbs/...",
            "_etag": "\"00000\"",
        }
        entity = BaseEntity.from_dict(data)
        assert entity.id == "test-1"
    
    def test_bump_version(self):
        """bump_version() increments version and updates audit"""
        entity = BaseEntity(id="test-1", name="Test", version=1)
        entity.bump_version("updater@test.com")
        assert entity.version == 2
        assert entity.modifiedBy == "updater@test.com"
        assert entity.modifiedDate != ""
    
    def test_validate_missing_id(self):
        """validate() catches missing id"""
        entity = BaseEntity(name="Test")
        errors = entity.validate()
        assert any("id" in e for e in errors)
    
    def test_validate_missing_name(self):
        """validate() catches missing name"""
        entity = BaseEntity(id="test-1")
        errors = entity.validate()
        assert any("name" in e for e in errors)
    
    def test_validate_invalid_status(self):
        """validate() catches invalid status"""
        entity = BaseEntity(id="test-1", name="Test", status="invalid")
        errors = entity.validate()
        assert any("status" in e for e in errors)
    
    def test_validate_valid_entity(self):
        """validate() passes for a valid entity"""
        entity = BaseEntity(id="test-1", name="Test", status="active")
        errors = entity.validate()
        assert len(errors) == 0
    
    def test_entity_status_enum(self):
        """EntityStatus enum has expected values"""
        assert EntityStatus.ACTIVE == "active"
        assert EntityStatus.DISABLED == "disabled"
        assert EntityStatus.STAGED == "staged"


# =============================================================================
# Rule Model Tests
# =============================================================================

class TestRule:
    """Tests for the Rule model"""
    
    def test_create_simple_rule(self):
        """Create a basic equals rule"""
        rule = Rule(
            id="rule-1",
            name="Milestone is null",
            field="Custom.MilestoneID",
            operator="isNull"
        )
        assert rule.field == "Custom.MilestoneID"
        assert rule.operator == "isNull"
        assert rule.value is None
    
    def test_validate_valid_rule(self):
        """Valid rule passes validation"""
        rule = Rule(
            id="rule-1",
            name="Test Rule",
            field="Custom.SolutionArea",
            operator="equals",
            value="AMEA"
        )
        errors = rule.validate()
        assert len(errors) == 0
    
    def test_validate_missing_field(self):
        """Rule without field fails validation"""
        rule = Rule(id="rule-1", name="Test", operator="equals", value="x")
        errors = rule.validate()
        assert any("field" in e for e in errors)
    
    def test_validate_missing_operator(self):
        """Rule without operator fails validation"""
        rule = Rule(id="rule-1", name="Test", field="f", value="x")
        errors = rule.validate()
        assert any("operator" in e for e in errors)
    
    def test_validate_invalid_operator(self):
        """Rule with unknown operator fails validation"""
        rule = Rule(
            id="rule-1", name="Test",
            field="f", operator="banana", value="x"
        )
        errors = rule.validate()
        assert any("Unknown operator" in e for e in errors)
    
    def test_validate_isNull_no_value(self):
        """isNull operator should not have a value"""
        rule = Rule(
            id="rule-1", name="Test",
            field="f", operator="isNull", value="oops"
        )
        errors = rule.validate()
        assert any("should not have a value" in e for e in errors)
    
    def test_validate_in_requires_list(self):
        """'in' operator requires a list value"""
        rule = Rule(
            id="rule-1", name="Test",
            field="f", operator="in", value="not_a_list"
        )
        errors = rule.validate()
        assert any("list" in e for e in errors)
    
    def test_validate_in_requires_nonempty_list(self):
        """'in' operator requires a non-empty list"""
        rule = Rule(
            id="rule-1", name="Test",
            field="f", operator="in", value=[]
        )
        errors = rule.validate()
        assert any("non-empty" in e for e in errors)
    
    def test_display_string_equals(self):
        """Display string for equals operator"""
        rule = Rule(
            id="r-1", name="T",
            field="Custom.Area", operator="equals", value="AMEA"
        )
        assert "equals" in rule.to_display_string()
        assert "AMEA" in rule.to_display_string()
    
    def test_display_string_isNull(self):
        """Display string for isNull operator"""
        rule = Rule(
            id="r-1", name="T",
            field="Custom.MilestoneID", operator="isNull"
        )
        display = rule.to_display_string()
        assert "isNull" in display
        assert "MilestoneID" in display
    
    def test_display_string_in(self):
        """Display string for 'in' operator shows list"""
        rule = Rule(
            id="r-1", name="T",
            field="Analysis.Category", operator="in",
            value=["Feature Request", "Capacity"]
        )
        display = rule.to_display_string()
        assert "in" in display
        assert "Feature Request" in display
    
    def test_round_trip_dict(self):
        """Rule survives to_dict/from_dict round trip"""
        rule = Rule(
            id="rule-1", name="Test",
            field="Custom.Area", operator="equals", value="AMEA"
        )
        d = rule.to_dict()
        restored = Rule.from_dict(d)
        assert restored.id == rule.id
        assert restored.field == rule.field
        assert restored.operator == rule.operator
        assert restored.value == rule.value
    
    def test_all_valid_operators(self):
        """All VALID_OPERATORS are accounted for"""
        assert len(VALID_OPERATORS) == 15
        assert "equals" in VALID_OPERATORS
        assert "isNull" in VALID_OPERATORS
        assert "under" in VALID_OPERATORS
        assert "matches" in VALID_OPERATORS


# =============================================================================
# Action Model Tests
# =============================================================================

class TestAction:
    """Tests for the Action model"""
    
    def test_create_set_action(self):
        """Create a basic 'set' action"""
        action = Action(
            id="action-1",
            name="Set Area Path",
            field="System.AreaPath",
            operation="set",
            value="UAT\\MCAPS\\AI"
        )
        assert action.operation == "set"
        assert action.value == "UAT\\MCAPS\\AI"
    
    def test_validate_valid_action(self):
        """Valid action passes validation"""
        action = Action(
            id="action-1", name="Test",
            field="System.AreaPath", operation="set",
            value="UAT\\MCAPS\\AI"
        )
        errors = action.validate()
        assert len(errors) == 0
    
    def test_validate_missing_field(self):
        """Action missing field fails validation"""
        action = Action(
            id="action-1", name="Test",
            operation="set", value="x"
        )
        errors = action.validate()
        assert any("field" in e for e in errors)
    
    def test_validate_invalid_operation(self):
        """Action with invalid operation fails validation"""
        action = Action(
            id="action-1", name="Test",
            field="f", operation="destroy", value="x"
        )
        errors = action.validate()
        assert any("Unknown operation" in e for e in errors)
    
    def test_validate_missing_value(self):
        """Action missing value fails validation"""
        action = Action(
            id="action-1", name="Test",
            field="f", operation="set"
        )
        errors = action.validate()
        assert any("value is required" in e for e in errors)
    
    def test_validate_copy_requires_string(self):
        """Copy operation value must be a string"""
        action = Action(
            id="action-1", name="Test",
            field="f", operation="copy", value=123
        )
        errors = action.validate()
        assert any("field name string" in e for e in errors)
    
    def test_validate_set_computed_known_functions(self):
        """set_computed must use a known function"""
        action = Action(
            id="action-1", name="Test",
            field="f", operation="set_computed", value="unknown()"
        )
        errors = action.validate()
        assert any("Unknown computed function" in e for e in errors)
    
    def test_display_string_set(self):
        """Display string for 'set' shows SET format"""
        action = Action(
            id="a-1", name="T",
            field="System.AreaPath", operation="set",
            value="UAT\\AI"
        )
        assert "SET" in action.to_display_string()
    
    def test_display_string_copy(self):
        """Display string for 'copy' shows FROM"""
        action = Action(
            id="a-1", name="T",
            field="System.AssignedTo", operation="copy",
            value="System.CreatedBy"
        )
        display = action.to_display_string()
        assert "COPY" in display
        assert "FROM" in display
    
    def test_display_string_template(self):
        """Display string for template shows TEMPLATE"""
        action = Action(
            id="a-1", name="T",
            field="Discussion", operation="template",
            value="{CreatedBy} - Please provide info"
        )
        assert "TEMPLATE" in action.to_display_string()
    
    def test_round_trip_dict(self):
        """Action survives to_dict/from_dict round trip"""
        action = Action(
            id="action-1", name="Test",
            field="System.AreaPath", operation="set",
            value="UAT\\AI"
        )
        d = action.to_dict()
        restored = Action.from_dict(d)
        assert restored.id == action.id
        assert restored.operation == action.operation
    
    def test_all_valid_operations(self):
        """VALID_OPERATIONS has expected entries"""
        assert len(VALID_OPERATIONS) == 5
        assert "set" in VALID_OPERATIONS
        assert "template" in VALID_OPERATIONS


# =============================================================================
# Trigger Model Tests
# =============================================================================

class TestTrigger:
    """Tests for the Trigger model"""
    
    def test_create_simple_trigger(self):
        """Create a trigger with AND expression"""
        trigger = Trigger(
            id="dt-10",
            name="No Milestone",
            priority=10,
            expression={"and": ["rule-1", "rule-3"]},
            onTrue="route-1"
        )
        assert trigger.priority == 10
        assert trigger.onTrue == "route-1"
    
    def test_validate_valid_trigger(self):
        """Valid trigger passes validation"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=10,
            expression={"and": ["rule-1", "rule-3"]},
            onTrue="route-1"
        )
        errors = trigger.validate()
        assert len(errors) == 0
    
    def test_validate_missing_expression(self):
        """Trigger without expression fails"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=10, expression={}, onTrue="route-1"
        )
        errors = trigger.validate()
        assert any("expression" in e for e in errors)
    
    def test_validate_missing_onTrue(self):
        """Trigger without onTrue fails"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=10,
            expression={"and": ["rule-1", "rule-3"]}
        )
        errors = trigger.validate()
        assert any("onTrue" in e for e in errors)
    
    def test_validate_invalid_priority(self):
        """Priority < 1 fails validation"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=0,
            expression={"and": ["rule-1", "rule-3"]},
            onTrue="route-1"
        )
        errors = trigger.validate()
        assert any("priority" in e for e in errors)
    
    def test_validate_and_needs_two_children(self):
        """AND expression needs at least 2 children"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=10,
            expression={"and": ["rule-1"]},
            onTrue="route-1"
        )
        errors = trigger.validate()
        assert any("at least 2" in e for e in errors)
    
    def test_validate_nested_expression(self):
        """Nested AND/OR expression validates"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=10,
            expression={"and": ["rule-2", {"or": ["rule-3", "rule-7"]}]},
            onTrue="route-1"
        )
        errors = trigger.validate()
        assert len(errors) == 0
    
    def test_validate_not_expression(self):
        """NOT expression validates"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=10,
            expression={"and": [{"not": "rule-2"}, "rule-9"]},
            onTrue="route-1"
        )
        errors = trigger.validate()
        assert len(errors) == 0
    
    def test_validate_invalid_operator(self):
        """Unknown operator fails validation"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=10,
            expression={"xor": ["rule-1", "rule-2"]},
            onTrue="route-1"
        )
        errors = trigger.validate()
        assert any("Unknown expression operator" in e for e in errors)
    
    def test_get_referenced_rule_ids_simple(self):
        """Extract rule IDs from simple AND"""
        trigger = Trigger(
            id="dt-10", name="Test",
            expression={"and": ["rule-1", "rule-3"]},
            onTrue="route-1"
        )
        ids = trigger.get_referenced_rule_ids()
        assert ids == {"rule-1", "rule-3"}
    
    def test_get_referenced_rule_ids_nested(self):
        """Extract rule IDs from nested expression"""
        trigger = Trigger(
            id="dt-10", name="Test",
            expression={
                "and": [
                    "rule-2",
                    {"or": ["rule-3", "rule-7"]},
                    {"not": "rule-5"}
                ]
            },
            onTrue="route-1"
        )
        ids = trigger.get_referenced_rule_ids()
        assert ids == {"rule-2", "rule-3", "rule-7", "rule-5"}
    
    def test_round_trip_dict(self):
        """Trigger survives to_dict/from_dict round trip"""
        trigger = Trigger(
            id="dt-10", name="Test",
            priority=10,
            expression={"and": ["rule-1", "rule-3"]},
            onTrue="route-1"
        )
        d = trigger.to_dict()
        restored = Trigger.from_dict(d)
        assert restored.id == trigger.id
        assert restored.expression == trigger.expression
        assert restored.onTrue == trigger.onTrue


# =============================================================================
# Route Model Tests
# =============================================================================

class TestRoute:
    """Tests for the Route model"""
    
    def test_create_route(self):
        """Create a route with actions"""
        route = Route(
            id="route-1",
            name="AI Triage",
            actions=["action-1", "action-2"]
        )
        assert len(route.actions) == 2
    
    def test_validate_valid_route(self):
        """Valid route passes validation"""
        route = Route(
            id="route-1", name="Test",
            actions=["action-1", "action-2"]
        )
        errors = route.validate()
        assert len(errors) == 0
    
    def test_validate_empty_actions(self):
        """Route with no actions fails"""
        route = Route(id="route-1", name="Test", actions=[])
        errors = route.validate()
        assert any("empty" in e for e in errors)
    
    def test_validate_duplicate_actions(self):
        """Route with duplicate action IDs fails"""
        route = Route(
            id="route-1", name="Test",
            actions=["action-1", "action-1"]
        )
        errors = route.validate()
        assert any("Duplicate" in e for e in errors)
    
    def test_add_action(self):
        """add_action() appends an action"""
        route = Route(
            id="route-1", name="Test",
            actions=["action-1"]
        )
        route.add_action("action-2")
        assert "action-2" in route.actions
    
    def test_add_duplicate_action_raises(self):
        """add_action() raises on duplicate"""
        route = Route(
            id="route-1", name="Test",
            actions=["action-1"]
        )
        with pytest.raises(ValueError, match="already in"):
            route.add_action("action-1")
    
    def test_remove_action(self):
        """remove_action() removes an action"""
        route = Route(
            id="route-1", name="Test",
            actions=["action-1", "action-2"]
        )
        route.remove_action("action-1")
        assert "action-1" not in route.actions
    
    def test_remove_missing_action_raises(self):
        """remove_action() raises if not found"""
        route = Route(
            id="route-1", name="Test",
            actions=["action-1"]
        )
        with pytest.raises(ValueError, match="not in"):
            route.remove_action("action-99")
    
    def test_get_referenced_action_ids(self):
        """get_referenced_action_ids() returns all action IDs"""
        route = Route(
            id="route-1", name="Test",
            actions=["action-1", "action-2", "action-3"]
        )
        ids = route.get_referenced_action_ids()
        assert ids == {"action-1", "action-2", "action-3"}
    
    def test_round_trip_dict(self):
        """Route survives to_dict/from_dict round trip"""
        route = Route(
            id="route-1", name="Test",
            actions=["action-1", "action-2"]
        )
        d = route.to_dict()
        restored = Route.from_dict(d)
        assert restored.actions == route.actions


# =============================================================================
# Evaluation Model Tests
# =============================================================================

class TestEvaluation:
    """Tests for the Evaluation model"""
    
    def test_analysis_state_constants(self):
        """AnalysisState has expected values"""
        assert AnalysisState.PENDING == "Pending"
        assert AnalysisState.APPROVED == "Approved"
        assert AnalysisState.NO_MATCH == "No Match"
        assert AnalysisState.ERROR == "Error"
    
    def test_terminal_states(self):
        """TERMINAL_STATES includes Approved and Override"""
        assert AnalysisState.APPROVED in AnalysisState.TERMINAL_STATES
        assert AnalysisState.OVERRIDE in AnalysisState.TERMINAL_STATES
    
    def test_retriggerable_states(self):
        """RETRIGGERABLE_STATES includes Pending and Needs Info"""
        assert AnalysisState.PENDING in AnalysisState.RETRIGGERABLE_STATES
        assert AnalysisState.NEEDS_INFO in AnalysisState.RETRIGGERABLE_STATES


# =============================================================================
# AnalysisResult Model Tests
# =============================================================================

class TestAnalysisResult:
    """Tests for the AnalysisResult model"""
    
    def test_get_analysis_field(self):
        """get_analysis_field() resolves known fields"""
        result = AnalysisResult(
            category="Feature Request",
            businessImpact="high"
        )
        assert result.get_analysis_field("Category") == "Feature Request"
        assert result.get_analysis_field("BusinessImpact") == "high"
    
    def test_get_analysis_field_unknown(self):
        """get_analysis_field() returns None for unknown fields"""
        result = AnalysisResult()
        assert result.get_analysis_field("NonExistent") is None


# =============================================================================
# AuditEntry Model Tests
# =============================================================================

class TestAuditEntry:
    """Tests for the AuditEntry model"""
    
    def test_create_factory(self):
        """AuditEntry.create() generates id and timestamp"""
        entry = AuditEntry.create(
            entity_type="rule",
            entity_id="rule-1",
            action=AuditAction.CREATE,
            actor="user@test.com"
        )
        assert entry.id.startswith("audit-")
        assert entry.entityType == "rule"
        assert entry.action == "rule.create"
    
    def test_audit_action_constants(self):
        """AuditAction has expected constants"""
        assert AuditAction.CREATE == "create"
        assert AuditAction.UPDATE == "update"
        assert AuditAction.DELETE == "delete"
