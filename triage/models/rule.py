"""
Rule Model
==========

Represents an atomic condition in the triage system.
A rule evaluates a single field against an operator and value,
producing a True or False result.

Examples:
    Rule: "Milestone ID is Null"
        field: "Custom.MilestoneID"
        operator: "isNull"
        value: None
    
    Rule: "Solution Area = AMEA"
        field: "Custom.SolutionArea"
        operator: "equals"
        value: "AMEA"
    
    Rule: "Analysis Category in [Feature Request, Capacity]"
        field: "Analysis.Category"
        operator: "in"
        value: ["Feature Request", "Capacity"]

Cosmos DB Container: rules
Partition Key: /status
"""

from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional

from .base import BaseEntity, EntityStatus


# =============================================================================
# Supported Operators
# =============================================================================
# Grouped by applicable field types. The rules engine uses this list to
# validate that an operator is valid for the given field type.

VALID_OPERATORS = [
    # String/All types
    "equals",
    "notEquals",
    "in",
    "notIn",
    "isNull",
    "isNotNull",
    
    # String-specific
    "contains",
    "notContains",
    "startsWith",
    "matches",       # Regex
    
    # Hierarchical tree path (e.g., Area Path)
    "under",
    
    # Numeric/Date comparisons
    "gt",
    "lt",
    "gte",
    "lte",
]


@dataclass
class Rule(BaseEntity):
    """
    An atomic rule that evaluates a single condition.
    
    A rule reads one field from a work item, applies an operator,
    and compares against a value to produce True or False.
    
    The rule is the smallest unit of logic in the triage system.
    Rules are combined into Triggers using AND/OR expressions.
    
    Attributes:
        field:    ADO field reference name (e.g., "Custom.MilestoneID")
        operator: Comparison operator (e.g., "equals", "isNull", "in")
        value:    Comparison value (type depends on operator):
                  - None for isNull/isNotNull
                  - str for equals, contains, startsWith, under, matches
                  - list for in, notIn
                  - number for gt, lt, gte, lte
                  
    Partition Key: status (active/disabled/staged)
    """
    
    # -------------------------------------------------------------------------
    # Rule Definition
    # -------------------------------------------------------------------------
    field: str = ""          # ADO field reference (e.g., "Custom.SolutionArea")
    operator: str = ""       # Comparison operator (see VALID_OPERATORS)
    value: Any = None        # Value to compare against (type varies by operator)
    
    def validate(self) -> List[str]:
        """
        Validate rule configuration.
        
        Checks:
            1. Base entity fields (id, name, status)
            2. Field reference is provided
            3. Operator is from the supported list
            4. Value is appropriate for the operator
        
        Returns:
            List of validation error strings (empty = valid)
        """
        errors = super().validate()
        
        # Field is required
        if not self.field:
            errors.append("field is required (e.g., 'Custom.SolutionArea')")
        
        # Operator must be from the known list
        if not self.operator:
            errors.append("operator is required")
        elif self.operator not in VALID_OPERATORS:
            errors.append(
                f"Unknown operator '{self.operator}'. "
                f"Valid operators: {VALID_OPERATORS}"
            )
        
        # Value validation based on operator
        if self.operator in ("isNull", "isNotNull"):
            # These operators don't use a value
            if self.value is not None:
                errors.append(
                    f"Operator '{self.operator}' should not have a value"
                )
        elif self.operator in ("in", "notIn"):
            # These require a list
            if not isinstance(self.value, list):
                errors.append(
                    f"Operator '{self.operator}' requires a list value"
                )
            elif len(self.value) == 0:
                errors.append(
                    f"Operator '{self.operator}' requires a non-empty list"
                )
        elif self.operator in ("gt", "lt", "gte", "lte"):
            # These require a numeric or date value
            if self.value is None:
                errors.append(
                    f"Operator '{self.operator}' requires a value"
                )
        elif self.operator in ("equals", "notEquals", "contains", "notContains",
                               "startsWith", "under", "matches"):
            # These require a non-null value
            if self.value is None:
                errors.append(
                    f"Operator '{self.operator}' requires a value"
                )
        
        return errors
    
    def to_display_string(self) -> str:
        """
        Human-readable representation of the rule condition.
        
        Examples:
            "Custom.MilestoneID isNull"
            "Custom.SolutionArea equals 'AMEA'"
            "Analysis.Category in ['Feature Request', 'Capacity']"
        
        Returns:
            Formatted string describing the rule
        """
        if self.operator in ("isNull", "isNotNull"):
            return f"{self.field} {self.operator}"
        elif isinstance(self.value, list):
            return f"{self.field} {self.operator} {self.value}"
        else:
            return f"{self.field} {self.operator} '{self.value}'"
    
    def __repr__(self) -> str:
        return (
            f"Rule(id='{self.id}', name='{self.name}', "
            f"condition='{self.to_display_string()}', "
            f"status='{self.status}')"
        )
