"""
Decision Tree Model
====================

Represents a decision tree that chains rules together with AND/OR logic
and maps to a route when the expression evaluates to True.

Trees are evaluated in priority order (lowest number = highest priority).
The first tree whose expression evaluates to True wins, and its route
is executed. There is no ELSE path - if no tree matches, the state
becomes "No Match" for manual triage.

Expression Format:
    Expressions are nested dicts using "and", "or", and "not" keys.
    Leaf nodes are rule ID strings.
    
    Simple AND:     {"and": ["rule-1", "rule-3"]}
    Simple OR:      {"or":  ["rule-3", "rule-7"]}
    Nested:         {"and": ["rule-2", {"or": ["rule-3", "rule-7"]}]}
    NOT:            {"and": [{"not": "rule-2"}, "rule-9"]}

Examples:
    Tree: "No Milestone Feature Request" (priority 10)
        expression: {"and": ["rule-1", "rule-3"]}
        onTrue: "route-1"
        Meaning: IF rule-1 AND rule-3 → execute route-1

    Tree: "Blocked Milestone with Feature/Capacity" (priority 20)
        expression: {"and": ["rule-2", {"or": ["rule-3", "rule-7"]}]}
        onTrue: "route-3"
        Meaning: IF rule-2 AND (rule-3 OR rule-7) → execute route-3

Cosmos DB Container: trees
Partition Key: /status
"""

from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional, Set

from .base import BaseEntity


@dataclass
class DecisionTree(BaseEntity):
    """
    A decision tree combining rules with AND/OR logic.
    
    Trees are the second layer of the four-layer model. They combine
    atomic rules into compound conditions using boolean expressions.
    
    Evaluation Rules:
        - Trees are processed in priority order (ascending: 10, 20, 30...)
        - First tree whose expression evaluates to True wins
        - If a disabled rule appears in an AND expression → tree = False
        - If a missing/deleted rule is referenced → ERROR state
        - If no tree matches → Analysis.State = "No Match"
    
    Attributes:
        priority:    Evaluation order (ascending, lower = higher priority)
        expression:  Nested AND/OR/NOT dict referencing rule IDs
        onTrue:      Route ID to execute when expression is True
        
    Partition Key: status (active/disabled/staged)
    """
    
    # -------------------------------------------------------------------------
    # Tree Definition
    # -------------------------------------------------------------------------
    priority: int = 100           # Evaluation order (lower = higher priority)
    expression: Dict = field(     # Nested AND/OR expression
        default_factory=dict
    )
    onTrue: str = ""              # Route ID to execute on True
    
    def validate(self) -> List[str]:
        """
        Validate tree configuration.
        
        Checks:
            1. Base entity fields (id, name, status)
            2. Priority is a positive integer
            3. Expression is non-empty and structurally valid
            4. onTrue route ID is specified
        
        Returns:
            List of validation error strings (empty = valid)
        """
        errors = super().validate()
        
        # Priority must be positive
        if self.priority < 1:
            errors.append("priority must be a positive integer")
        
        # Expression is required and must be valid
        if not self.expression:
            errors.append("expression is required (cannot be empty)")
        else:
            expr_errors = self._validate_expression(self.expression)
            errors.extend(expr_errors)
        
        # Route reference is required
        if not self.onTrue:
            errors.append("onTrue route ID is required")
        
        return errors
    
    def _validate_expression(self, expr: Any, depth: int = 0) -> List[str]:
        """
        Recursively validate the expression structure.
        
        Valid structures:
            - String (rule ID reference): "rule-1"
            - AND: {"and": [<expr>, <expr>, ...]}
            - OR:  {"or":  [<expr>, <expr>, ...]}
            - NOT: {"not": <expr>}
        
        Args:
            expr:  Expression node to validate
            depth: Current nesting depth (for error messages)
            
        Returns:
            List of validation error strings
        """
        errors = []
        
        # Guard against excessive nesting (likely a mistake)
        if depth > 10:
            errors.append("Expression nesting too deep (max 10 levels)")
            return errors
        
        if isinstance(expr, str):
            # Leaf node: must be a non-empty rule ID
            if not expr:
                errors.append("Empty rule ID in expression")
            return errors
        
        if isinstance(expr, dict):
            # Must have exactly one key: "and", "or", or "not"
            keys = list(expr.keys())
            
            if len(keys) != 1:
                errors.append(
                    f"Expression node must have exactly one key "
                    f"('and', 'or', or 'not'), got: {keys}"
                )
                return errors
            
            key = keys[0]
            
            if key == "not":
                # NOT takes a single expression
                errors.extend(
                    self._validate_expression(expr["not"], depth + 1)
                )
            elif key in ("and", "or"):
                # AND/OR take a list of expressions
                children = expr[key]
                if not isinstance(children, list):
                    errors.append(
                        f"'{key}' must contain a list of expressions"
                    )
                elif len(children) < 2:
                    errors.append(
                        f"'{key}' must have at least 2 child expressions"
                    )
                else:
                    for i, child in enumerate(children):
                        child_errors = self._validate_expression(
                            child, depth + 1
                        )
                        errors.extend(child_errors)
            else:
                errors.append(
                    f"Unknown expression operator '{key}'. "
                    f"Must be 'and', 'or', or 'not'"
                )
        else:
            errors.append(
                f"Invalid expression type: {type(expr).__name__}. "
                f"Expected string (rule ID) or dict (and/or/not)"
            )
        
        return errors
    
    def get_referenced_rule_ids(self) -> Set[str]:
        """
        Extract all rule IDs referenced in this tree's expression.
        
        Useful for:
            - Validating that all referenced rules exist
            - Building "used in" reference tracking
            - Detecting orphaned rules
        
        Returns:
            Set of rule ID strings (e.g., {"rule-1", "rule-3"})
        """
        rule_ids = set()
        self._collect_rule_ids(self.expression, rule_ids)
        return rule_ids
    
    def _collect_rule_ids(self, expr: Any, rule_ids: Set[str]) -> None:
        """Recursively collect all rule IDs from an expression tree"""
        if isinstance(expr, str):
            # Leaf node = rule ID
            rule_ids.add(expr)
        elif isinstance(expr, dict):
            key = list(expr.keys())[0]
            if key == "not":
                self._collect_rule_ids(expr["not"], rule_ids)
            elif key in ("and", "or"):
                for child in expr[key]:
                    self._collect_rule_ids(child, rule_ids)
    
    def get_referenced_route_id(self) -> Optional[str]:
        """Get the route ID this tree maps to on True"""
        return self.onTrue if self.onTrue else None
    
    def to_display_string(self) -> str:
        """
        Human-readable representation of the tree expression.
        
        Examples:
            "Priority 10: rule-1 AND rule-3 → route-1"
            "Priority 20: rule-2 AND (rule-3 OR rule-7) → route-3"
        
        Returns:
            Formatted string describing the tree
        """
        expr_str = self._expression_to_string(self.expression)
        return f"Priority {self.priority}: {expr_str} → {self.onTrue}"
    
    def _expression_to_string(self, expr: Any) -> str:
        """Recursively convert expression tree to readable string"""
        if isinstance(expr, str):
            return expr
        
        if isinstance(expr, dict):
            key = list(expr.keys())[0]
            
            if key == "not":
                inner = self._expression_to_string(expr["not"])
                return f"NOT {inner}"
            elif key in ("and", "or"):
                children = [
                    self._expression_to_string(child)
                    for child in expr[key]
                ]
                sep = f" {key.upper()} "
                result = sep.join(children)
                # Wrap in parens if nested
                return f"({result})" if len(children) > 1 else result
        
        return str(expr)
    
    def __repr__(self) -> str:
        rule_count = len(self.get_referenced_rule_ids())
        return (
            f"DecisionTree(id='{self.id}', name='{self.name}', "
            f"priority={self.priority}, rules={rule_count}, "
            f"onTrue='{self.onTrue}', status='{self.status}')"
        )
