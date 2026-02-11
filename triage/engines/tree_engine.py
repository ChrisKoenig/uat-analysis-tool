"""
Decision Tree Engine
====================

Walks decision trees in priority order using pre-computed rule results.
The first tree whose expression evaluates to True wins, and its route
is selected for execution.

This is Layer 2 of the four-layer model. It consumes the output of the
Rules Engine (Layer 1) - a dict of {ruleId: T/F} - and produces a
routing decision: which route to execute, or "No Match".

Evaluation Logic:
    1. Sort all active trees by priority (ascending)
    2. For each tree, evaluate its expression using stored rule results
    3. First tree that evaluates to True → return its onTrue route
    4. If no tree matches → return None (state becomes "No Match")

Expression Evaluation Rules:
    - AND: All children must be True (short-circuits on first False)
    - OR:  Any child must be True (short-circuits on first True)
    - NOT: Inverts the child result
    - Leaf (rule ID): Looks up the stored T/F result
    
Special Cases:
    - Disabled rule in AND expression → tree evaluates as False
      (conservative: prevents incorrect routing)
    - Missing rule (not in results and not skipped) → ERROR
      (data integrity issue, should not happen)
    - Disabled rule in OR expression → treated as False
      (remaining rules can still satisfy the OR)
"""

from typing import Dict, List, Optional, Tuple, Any
import logging

from ..models.tree import DecisionTree

logger = logging.getLogger("triage.engines.tree")


class TreeEngine:
    """
    Evaluates decision trees using pre-computed rule results.
    
    Usage:
        engine = TreeEngine()
        
        # Find the winning tree and its route
        matched_tree, route_id, errors = engine.evaluate(
            trees=active_trees,
            rule_results={"rule-1": True, "rule-3": False, ...},
            skipped_rules=["rule-4"]
        )
        
        # matched_tree = "dt-10" (or None if no match)
        # route_id = "route-1" (or None if no match)
        # errors = [] (or list of error messages)
    """
    
    def evaluate(
        self,
        trees: List[DecisionTree],
        rule_results: Dict[str, bool],
        skipped_rules: Optional[List[str]] = None,
        include_staged: bool = False
    ) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Walk decision trees in priority order, returning the first match.
        
        Args:
            trees:          List of decision trees to evaluate
            rule_results:   Pre-computed rule results {ruleId: T/F}
            skipped_rules:  Rule IDs that were skipped (disabled/error)
            include_staged: If True, include staged trees (dry-run mode)
            
        Returns:
            Tuple of:
                - Tree ID that matched (or None)
                - Route ID to execute (or None)
                - List of error/warning messages
        """
        skipped = set(skipped_rules or [])
        errors: List[str] = []
        
        # Determine which statuses participate in evaluation.
        # In dry-run/test mode, include_staged=True adds staged trees.
        allowed_statuses = {"active"}
        if include_staged:
            allowed_statuses.add("staged")
        
        eligible_trees = [t for t in trees if t.status in allowed_statuses]
        sorted_trees = sorted(eligible_trees, key=lambda t: t.priority)
        
        logger.info(
            "evaluate: %d total trees, %d eligible (allowed=%s), "
            "%d rule results, %d skipped rules",
            len(trees), len(sorted_trees), allowed_statuses,
            len(rule_results), len(skipped),
        )
        
        for tree in sorted_trees:
            logger.debug(
                "  tree '%s' (priority=%d): evaluating expression...",
                tree.id, tree.priority,
            )
            try:
                result = self._evaluate_expression(
                    tree.expression,
                    rule_results,
                    skipped,
                    tree.id
                )
                
                logger.debug(
                    "  tree '%s' → %s (route=%s)",
                    tree.id, result, tree.onTrue if result else "n/a",
                )
                
                if result is True:
                    # First match wins - return this tree's route
                    logger.info(
                        "evaluate: MATCH tree '%s' (priority=%d) → route '%s'",
                        tree.id, tree.priority, tree.onTrue,
                    )
                    return tree.id, tree.onTrue, errors
                    
            except MissingRuleError as e:
                # Missing rule is a data integrity error - log and continue
                logger.warning("  tree '%s' missing rule: %s", tree.id, e)
                errors.append(str(e))
                continue
            except Exception as e:
                logger.error(
                    "  tree '%s' evaluation error: %s", tree.id, e, exc_info=True,
                )
                errors.append(
                    f"Error evaluating tree '{tree.id}': {e}"
                )
                continue
        
        # No tree matched
        logger.info("evaluate: NO MATCH — %d trees evaluated, none matched", len(sorted_trees))
        return None, None, errors
    
    def evaluate_single(
        self,
        tree: DecisionTree,
        rule_results: Dict[str, bool],
        skipped_rules: Optional[List[str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Evaluate a single tree's expression (for testing/preview).
        
        Args:
            tree:          Decision tree to evaluate
            rule_results:  Pre-computed rule results
            skipped_rules: Skipped rule IDs
            
        Returns:
            Tuple of (True/False result, list of errors)
        """
        skipped = set(skipped_rules or [])
        errors: List[str] = []
        
        try:
            result = self._evaluate_expression(
                tree.expression,
                rule_results,
                skipped,
                tree.id
            )
            return result, errors
        except Exception as e:
            errors.append(str(e))
            return False, errors
    
    def _evaluate_expression(
        self,
        expr: Any,
        rule_results: Dict[str, bool],
        skipped_rules: set,
        tree_id: str
    ) -> bool:
        """
        Recursively evaluate an expression tree.
        
        Expression format:
            - String: rule ID → look up in rule_results
            - {"and": [...]}: All children must be True
            - {"or":  [...]}: Any child must be True
            - {"not": expr}:  Invert the child result
        
        Args:
            expr:          Expression node to evaluate
            rule_results:  Pre-computed rule results
            skipped_rules: Set of skipped rule IDs
            tree_id:       Tree ID (for error messages)
            
        Returns:
            True or False
            
        Raises:
            MissingRuleError: If a referenced rule has no result and isn't skipped
        """
        # -----------------------------------------------------------------
        # Leaf node: rule ID reference
        # -----------------------------------------------------------------
        if isinstance(expr, str):
            rule_id = expr
            
            # Check if the rule was skipped (disabled)
            if rule_id in skipped_rules:
                # Disabled rule → treated as False
                logger.debug(
                    "    leaf '%s' → False (rule disabled/skipped)", rule_id,
                )
                return False
            
            # Look up the rule's result
            if rule_id in rule_results:
                val = rule_results[rule_id]
                logger.debug("    leaf '%s' → %s", rule_id, val)
                return val
            
            # Rule not found in results OR skipped → data integrity error
            raise MissingRuleError(
                f"Tree '{tree_id}' references rule '{rule_id}' which has "
                f"no evaluation result and was not skipped. "
                f"This rule may have been deleted."
            )
        
        # -----------------------------------------------------------------
        # Compound node: AND, OR, NOT
        # -----------------------------------------------------------------
        if isinstance(expr, dict):
            key = list(expr.keys())[0]
            
            if key == "and":
                # AND: all children must be True
                logger.debug("    AND node (%d children)", len(expr["and"]))
                result = all(
                    self._evaluate_expression(
                        child, rule_results, skipped_rules, tree_id
                    )
                    for child in expr["and"]
                )
                logger.debug("    AND → %s", result)
                return result
            
            elif key == "or":
                # OR: any child must be True
                logger.debug("    OR node (%d children)", len(expr["or"]))
                result = any(
                    self._evaluate_expression(
                        child, rule_results, skipped_rules, tree_id
                    )
                    for child in expr["or"]
                )
                logger.debug("    OR → %s", result)
                return result
            
            elif key == "not":
                # NOT: invert the child result
                child_result = self._evaluate_expression(
                    expr["not"], rule_results, skipped_rules, tree_id
                )
                logger.debug("    NOT(%s) → %s", child_result, not child_result)
                return not child_result
            
            else:
                raise ValueError(
                    f"Unknown expression operator '{key}' in tree '{tree_id}'"
                )
        
        # Unexpected type
        raise ValueError(
            f"Invalid expression type in tree '{tree_id}': "
            f"{type(expr).__name__}"
        )
    
    def get_evaluation_trace(
        self,
        trees: List[DecisionTree],
        rule_results: Dict[str, bool],
        skipped_rules: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all trees and return detailed trace information.
        
        Unlike evaluate() which stops at the first match, this evaluates
        ALL trees to show how each one would have resolved. Useful for
        testing, debugging, and the admin UI preview.
        
        Args:
            trees:         List of trees to trace
            rule_results:  Pre-computed rule results
            skipped_rules: Skipped rule IDs
            
        Returns:
            List of dicts, one per tree, with evaluation details:
            [
                {
                    "treeId": "dt-10",
                    "priority": 10,
                    "result": True,
                    "routeId": "route-1",
                    "isWinner": True,
                    "error": None
                },
                ...
            ]
        """
        skipped = set(skipped_rules or [])
        trace = []
        winner_found = False
        
        active_trees = [t for t in trees if t.status == "active"]
        sorted_trees = sorted(active_trees, key=lambda t: t.priority)
        
        logger.debug(
            "get_evaluation_trace: %d active trees, %d rule results",
            len(sorted_trees), len(rule_results),
        )
        
        for tree in sorted_trees:
            entry = {
                "treeId": tree.id,
                "treeName": tree.name,
                "priority": tree.priority,
                "result": False,
                "routeId": tree.onTrue,
                "isWinner": False,
                "error": None,
            }
            
            try:
                result = self._evaluate_expression(
                    tree.expression,
                    rule_results,
                    skipped,
                    tree.id
                )
                entry["result"] = result
                
                # First True match is the winner
                if result and not winner_found:
                    entry["isWinner"] = True
                    winner_found = True
                    
            except Exception as e:
                entry["error"] = str(e)
            
            trace.append(entry)
        
        return trace


class MissingRuleError(Exception):
    """
    Raised when a decision tree references a rule that has no
    evaluation result and was not in the skipped list.
    
    This indicates a data integrity issue - the rule may have been
    deleted while still referenced by a tree.
    """
    pass
