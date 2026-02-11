"""
Trigger Engine
==============

Walks triggers in priority order using pre-computed rule results.
The first trigger whose expression evaluates to True wins, and its route
is selected for execution.

This is Layer 2 of the four-layer model. It consumes the output of the
Rules Engine (Layer 1) - a dict of {ruleId: T/F} - and produces a
routing decision: which route to execute, or "No Match".

Evaluation Logic:
    1. Sort all active triggers by priority (ascending)
    2. For each trigger, evaluate its expression using stored rule results
    3. First trigger that evaluates to True → return its onTrue route
    4. If no trigger matches → return None (state becomes "No Match")

Expression Evaluation Rules:
    - AND: All children must be True (short-circuits on first False)
    - OR:  Any child must be True (short-circuits on first True)
    - NOT: Inverts the child result
    - Leaf (rule ID): Looks up the stored T/F result
    
Special Cases:
    - Disabled rule in AND expression → trigger evaluates as False
      (conservative: prevents incorrect routing)
    - Missing rule (not in results and not skipped) → ERROR
      (data integrity issue, should not happen)
    - Disabled rule in OR expression → treated as False
      (remaining rules can still satisfy the OR)
"""

from typing import Dict, List, Optional, Tuple, Any
import logging

from ..models.trigger import Trigger

logger = logging.getLogger("triage.engines.trigger")


class TriggerEngine:
    """
    Evaluates triggers using pre-computed rule results.
    
    Usage:
        engine = TriggerEngine()
        
        # Find the winning trigger and its route
        matched_trigger, route_id, errors = engine.evaluate(
            triggers=active_triggers,
            rule_results={"rule-1": True, "rule-3": False, ...},
            skipped_rules=["rule-4"]
        )
        
        # matched_trigger = "dt-10" (or None if no match)
        # route_id = "route-1" (or None if no match)
        # errors = [] (or list of error messages)
    """
    
    def evaluate(
        self,
        triggers: List[Trigger],
        rule_results: Dict[str, bool],
        skipped_rules: Optional[List[str]] = None,
        include_staged: bool = False
    ) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Walk triggers in priority order, returning the first match.
        
        Args:
            triggers:       List of triggers to evaluate
            rule_results:   Pre-computed rule results {ruleId: T/F}
            skipped_rules:  Rule IDs that were skipped (disabled/error)
            include_staged: If True, include staged triggers (dry-run mode)
            
        Returns:
            Tuple of:
                - Trigger ID that matched (or None)
                - Route ID to execute (or None)
                - List of error/warning messages
        """
        skipped = set(skipped_rules or [])
        errors: List[str] = []
        
        # Determine which statuses participate in evaluation.
        # In dry-run/test mode, include_staged=True adds staged triggers.
        allowed_statuses = {"active"}
        if include_staged:
            allowed_statuses.add("staged")
        
        eligible_triggers = [t for t in triggers if t.status in allowed_statuses]
        sorted_triggers = sorted(eligible_triggers, key=lambda t: t.priority)
        
        logger.info(
            "evaluate: %d total triggers, %d eligible (allowed=%s), "
            "%d rule results, %d skipped rules",
            len(triggers), len(sorted_triggers), allowed_statuses,
            len(rule_results), len(skipped),
        )
        
        for trigger in sorted_triggers:
            logger.debug(
                "  trigger '%s' (priority=%d): evaluating expression...",
                trigger.id, trigger.priority,
            )
            try:
                result = self._evaluate_expression(
                    trigger.expression,
                    rule_results,
                    skipped,
                    trigger.id
                )
                
                logger.debug(
                    "  trigger '%s' → %s (route=%s)",
                    trigger.id, result, trigger.onTrue if result else "n/a",
                )
                
                if result is True:
                    # First match wins - return this trigger's route
                    logger.info(
                        "evaluate: MATCH trigger '%s' (priority=%d) → route '%s'",
                        trigger.id, trigger.priority, trigger.onTrue,
                    )
                    return trigger.id, trigger.onTrue, errors
                    
            except MissingRuleError as e:
                # Missing rule is a data integrity error - log and continue
                logger.warning("  trigger '%s' missing rule: %s", trigger.id, e)
                errors.append(str(e))
                continue
            except Exception as e:
                logger.error(
                    "  trigger '%s' evaluation error: %s", trigger.id, e, exc_info=True,
                )
                errors.append(
                    f"Error evaluating trigger '{trigger.id}': {e}"
                )
                continue
        
        # No trigger matched
        logger.info("evaluate: NO MATCH — %d triggers evaluated, none matched", len(sorted_triggers))
        return None, None, errors
    
    def evaluate_single(
        self,
        trigger: Trigger,
        rule_results: Dict[str, bool],
        skipped_rules: Optional[List[str]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Evaluate a single trigger's expression (for testing/preview).
        
        Args:
            trigger:       Trigger to evaluate
            rule_results:  Pre-computed rule results
            skipped_rules: Skipped rule IDs
            
        Returns:
            Tuple of (True/False result, list of errors)
        """
        skipped = set(skipped_rules or [])
        errors: List[str] = []
        
        try:
            result = self._evaluate_expression(
                trigger.expression,
                rule_results,
                skipped,
                trigger.id
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
        trigger_id: str
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
            trigger_id:    Trigger ID (for error messages)
            
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
                f"Trigger '{trigger_id}' references rule '{rule_id}' which has "
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
                        child, rule_results, skipped_rules, trigger_id
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
                        child, rule_results, skipped_rules, trigger_id
                    )
                    for child in expr["or"]
                )
                logger.debug("    OR → %s", result)
                return result
            
            elif key == "not":
                # NOT: invert the child result
                child_result = self._evaluate_expression(
                    expr["not"], rule_results, skipped_rules, trigger_id
                )
                logger.debug("    NOT(%s) → %s", child_result, not child_result)
                return not child_result
            
            else:
                raise ValueError(
                    f"Unknown expression operator '{key}' in trigger '{trigger_id}'"
                )
        
        # Unexpected type
        raise ValueError(
            f"Invalid expression type in trigger '{trigger_id}': "
            f"{type(expr).__name__}"
        )
    
    def get_evaluation_trace(
        self,
        triggers: List[Trigger],
        rule_results: Dict[str, bool],
        skipped_rules: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluate all triggers and return detailed trace information.
        
        Unlike evaluate() which stops at the first match, this evaluates
        ALL triggers to show how each one would have resolved. Useful for
        testing, debugging, and the admin UI preview.
        
        Args:
            triggers:      List of triggers to trace
            rule_results:  Pre-computed rule results
            skipped_rules: Skipped rule IDs
            
        Returns:
            List of dicts, one per trigger, with evaluation details:
            [
                {
                    "triggerId": "dt-10",
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
        
        active_triggers = [t for t in triggers if t.status == "active"]
        sorted_triggers = sorted(active_triggers, key=lambda t: t.priority)
        
        logger.debug(
            "get_evaluation_trace: %d active triggers, %d rule results",
            len(sorted_triggers), len(rule_results),
        )
        
        for trigger in sorted_triggers:
            entry = {
                "triggerId": trigger.id,
                "triggerName": trigger.name,
                "priority": trigger.priority,
                "result": False,
                "routeId": trigger.onTrue,
                "isWinner": False,
                "error": None,
            }
            
            try:
                result = self._evaluate_expression(
                    trigger.expression,
                    rule_results,
                    skipped,
                    trigger.id
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
    Raised when a trigger references a rule that has no
    evaluation result and was not in the skipped list.
    
    This indicates a data integrity issue - the rule may have been
    deleted while still referenced by a trigger.
    """
    pass
