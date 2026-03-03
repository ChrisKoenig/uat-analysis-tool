"""
Rules Engine
============

Evaluates atomic rules against work item data.
Each rule reads one field, applies an operator, and returns True or False.

This is Layer 1 of the four-layer model. The rules engine evaluates
ALL active rules against a work item, producing a dict of {ruleId: T/F}.
These results are then consumed by the Trigger Engine (Layer 2).

Evaluation Process:
    1. Load all active rules from Cosmos DB
    2. For each rule, resolve the field value from the work item data
    3. Apply the operator to compare field value vs rule value
    4. Store True/False result for each rule
    5. Track skipped rules (disabled, errors) separately

Operator Implementation:
    - equals/notEquals: Exact match (case-insensitive for strings)
    - in/notIn: Value membership in a list
    - contains/notContains: Substring search (case-insensitive)
    - startsWith: Prefix match (case-insensitive)
    - under: Hierarchical path match (e.g., "UAT\\MCAPS" under "UAT")
    - matches: Regex pattern match
    - isNull/isNotNull: Null/empty check
    - gt/lt/gte/lte: Numeric/date comparisons

Field Resolution:
    - ADO fields: Resolved from work item data dict
    - Analysis.* fields: Resolved from AnalysisResult object
    - Discussion: Special handling for comment threads
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple

from ..models.rule import Rule, VALID_OPERATORS
from ..models.analysis_result import AnalysisResult

logger = logging.getLogger("triage.engines.rules")


class RulesEngine:
    """
    Evaluates atomic rules against work item data.
    
    Usage:
        engine = RulesEngine()
        
        # Evaluate all rules against a work item
        results, skipped = engine.evaluate_all(
            rules=active_rules,
            work_item=work_item_data,
            analysis=analysis_result
        )
        
        # results = {"rule-1": True, "rule-3": False, ...}
        # skipped = ["rule-4"]  (disabled rules)
        
        # Evaluate a single rule
        result = engine.evaluate_rule(rule, work_item_data, analysis)
    """
    
    def evaluate_all(
        self,
        rules: List[Rule],
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult] = None,
        include_staged: bool = False
    ) -> Tuple[Dict[str, bool], List[str]]:
        """
        Evaluate ALL rules against a work item.
        
        Evaluates every active rule, storing True/False for each.
        Disabled rules are tracked in the skipped list.
        Rules that error during evaluation are also skipped.
        
        In test/dry-run mode (include_staged=True), staged rules are
        also evaluated alongside active rules.
        
        Args:
            rules:          List of all rules to evaluate
            work_item:      Work item data dict (field ref name → value)
            analysis:       Analysis result (for Analysis.* field lookups)
            include_staged: If True, evaluate staged rules too (dry-run mode)
            
        Returns:
            Tuple of:
                - Dict[str, bool]: rule ID → True/False for each evaluated rule
                - List[str]: rule IDs that were skipped (disabled/error)
        """
        # Determine which statuses participate in evaluation
        allowed_statuses = {"active"}
        if include_staged:
            allowed_statuses.add("staged")
        
        logger.info(
            "evaluate_all: %d rules, include_staged=%s, allowed=%s",
            len(rules), include_staged, allowed_statuses,
        )
        
        results: Dict[str, bool] = {}
        skipped: List[str] = []
        
        for rule in rules:
            # Skip rules that aren't in the allowed set
            if rule.status not in allowed_statuses:
                logger.debug(
                    "  SKIP rule '%s' (status=%s, not in %s)",
                    rule.id, rule.status, allowed_statuses,
                )
                skipped.append(rule.id)
                continue
            
            try:
                result = self.evaluate_rule(rule, work_item, analysis)
                results[rule.id] = result
                logger.debug(
                    "  rule '%s' [%s %s %s] → %s",
                    rule.id, rule.field, rule.operator, rule.value, result,
                )
            except Exception as e:
                # Rule evaluation error - skip it and log
                logger.error(
                    "  ERROR evaluating rule '%s': %s", rule.id, e, exc_info=True,
                )
                skipped.append(rule.id)
        
        true_count = sum(1 for v in results.values() if v)
        logger.info(
            "evaluate_all complete: %d evaluated (%d true, %d false), %d skipped",
            len(results), true_count, len(results) - true_count, len(skipped),
        )
        return results, skipped
    
    def evaluate_rule(
        self,
        rule: Rule,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult] = None
    ) -> bool:
        """
        Evaluate a single rule against work item data.
        
        Resolves the field value, then applies the operator.
        For containsAny, resolves multiple fields and checks if
        any field contains any of the keywords.
        
        Args:
            rule:      The rule to evaluate
            work_item: Work item data dict
            analysis:  Analysis result for Analysis.* fields
            
        Returns:
            True if the condition is met, False otherwise
            
        Raises:
            ValueError: If the operator is unknown
            Exception: If field resolution or comparison fails
        """
        # Special handling for multi-field operators
        if rule.operator == "containsAny":
            return self._evaluate_contains_any(rule, work_item, analysis)
        if rule.operator == "regexMatchAny":
            return self._evaluate_regex_match_any(rule, work_item, analysis)
        
        # Step 1: Resolve the field value from work item or analysis data
        field_value = self._resolve_field(
            rule.field, work_item, analysis
        )
        logger.debug(
            "    resolve '%s' → %r", rule.field, field_value,
        )
        
        # Step 2: Apply the operator
        result = self._apply_operator(
            rule.operator, field_value, rule.value
        )
        logger.debug(
            "    apply %s(%r, %r) → %s", rule.operator, field_value, rule.value, result,
        )
        return result
    
    def _resolve_field(
        self,
        field_ref: str,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult] = None
    ) -> Any:
        """
        Resolve a field reference to its actual value.
        
        Field sources:
            - "Analysis.*": Resolved from the AnalysisResult object
            - Everything else: Resolved from the work_item dict
        
        Args:
            field_ref:  Field reference name (e.g., "Custom.SolutionArea")
            work_item:  Work item data dict
            analysis:   Analysis result object
            
        Returns:
            The resolved field value (may be None if field doesn't exist)
        """
        # Analysis fields are prefixed with "Analysis."
        if field_ref.startswith("Analysis."):
            if analysis is None:
                return None
            # Strip "Analysis." prefix and resolve from the analysis result
            analysis_field = field_ref[len("Analysis."):]
            return analysis.get_analysis_field(analysis_field)
        
        # Standard ADO fields - look up in work item dict
        # Try exact match first, then case-insensitive fallback
        if field_ref in work_item:
            return work_item[field_ref]
        
        # Case-insensitive lookup (ADO field names can vary in casing)
        field_lower = field_ref.lower()
        for key, value in work_item.items():
            if key.lower() == field_lower:
                return value
        
        # Field not found in work item data
        return None
    
    def _apply_operator(
        self,
        operator: str,
        field_value: Any,
        rule_value: Any
    ) -> bool:
        """
        Apply a comparison operator to a field value and rule value.
        
        Handles type coercion, case-insensitive string comparisons,
        and null-safe operations.
        
        Args:
            operator:    Comparison operator (e.g., "equals", "in")
            field_value: Actual value from the work item
            rule_value:  Expected value from the rule definition
            
        Returns:
            True if the condition is satisfied
            
        Raises:
            ValueError: If the operator is not recognized
        """
        # Dispatch to the appropriate operator handler
        operator_handlers = {
            "equals": self._op_equals,
            "notEquals": self._op_not_equals,
            "in": self._op_in,
            "notIn": self._op_not_in,
            "contains": self._op_contains,
            "containsAny": self._op_contains_any,
            "notContains": self._op_not_contains,
            "startsWith": self._op_starts_with,
            "under": self._op_under,
            "matches": self._op_matches,
            "isNull": self._op_is_null,
            "isNotNull": self._op_is_not_null,
            "gt": self._op_gt,
            "lt": self._op_lt,
            "gte": self._op_gte,
            "lte": self._op_lte,
        }
        
        handler = operator_handlers.get(operator)
        if handler is None:
            raise ValueError(
                f"Unknown operator: '{operator}'. "
                f"Valid operators: {list(operator_handlers.keys())}"
            )
        
        return handler(field_value, rule_value)
    
    # =========================================================================
    # Operator Implementations
    # =========================================================================
    
    def _op_equals(self, field_value: Any, rule_value: Any) -> bool:
        """
        Exact match comparison.
        
        Case-insensitive for strings. None equals None.
        """
        if field_value is None and rule_value is None:
            return True
        if field_value is None or rule_value is None:
            return False
        
        # Case-insensitive string comparison
        if isinstance(field_value, str) and isinstance(rule_value, str):
            return field_value.lower() == rule_value.lower()
        
        return field_value == rule_value
    
    def _op_not_equals(self, field_value: Any, rule_value: Any) -> bool:
        """Not equal - inverse of equals"""
        return not self._op_equals(field_value, rule_value)
    
    def _op_in(self, field_value: Any, rule_value: Any) -> bool:
        """
        Value membership in a list.
        
        Case-insensitive for strings.
        If field_value is a list, checks for any overlap.
        """
        if field_value is None or rule_value is None:
            return False
        
        if not isinstance(rule_value, list):
            return False
        
        # If field value is a list (e.g., products), check for any overlap
        if isinstance(field_value, list):
            field_lower = {
                v.lower() if isinstance(v, str) else v
                for v in field_value
            }
            rule_lower = {
                v.lower() if isinstance(v, str) else v
                for v in rule_value
            }
            return bool(field_lower & rule_lower)
        
        # Single value check - case-insensitive for strings
        if isinstance(field_value, str):
            field_lower = field_value.lower()
            return any(
                (isinstance(v, str) and v.lower() == field_lower) or
                (not isinstance(v, str) and v == field_value)
                for v in rule_value
            )
        
        return field_value in rule_value
    
    def _op_not_in(self, field_value: Any, rule_value: Any) -> bool:
        """Not in list - inverse of in"""
        return not self._op_in(field_value, rule_value)
    
    def _op_contains(self, field_value: Any, rule_value: Any) -> bool:
        """
        Substring search (case-insensitive).
        
        If field_value is a list, checks if any element contains the substring.
        """
        if field_value is None or rule_value is None:
            return False
        
        rule_str = str(rule_value).lower()
        
        # List field: check if any element contains the substring
        if isinstance(field_value, list):
            return any(
                rule_str in str(v).lower()
                for v in field_value
            )
        
        return rule_str in str(field_value).lower()
    
    def _op_not_contains(self, field_value: Any, rule_value: Any) -> bool:
        """Substring not found - inverse of contains"""
        return not self._op_contains(field_value, rule_value)
    
    def _op_starts_with(self, field_value: Any, rule_value: Any) -> bool:
        """Prefix match (case-insensitive)"""
        if field_value is None or rule_value is None:
            return False
        return str(field_value).lower().startswith(str(rule_value).lower())
    
    def _op_under(self, field_value: Any, rule_value: Any) -> bool:
        """
        Hierarchical path match.
        
        Used for Area Path and Iteration Path. Checks if the field value
        is at or below the specified path in the hierarchy.
        
        Example: "UAT\\MCAPS\\AI" is under "UAT\\MCAPS"
                 "UAT\\MCAPS" is under "UAT\\MCAPS" (exact match)
                 "UAT\\Other" is NOT under "UAT\\MCAPS"
        """
        if field_value is None or rule_value is None:
            return False
        
        field_str = str(field_value).lower().replace("/", "\\")
        rule_str = str(rule_value).lower().replace("/", "\\")
        
        # Exact match or is a child path
        return (
            field_str == rule_str or
            field_str.startswith(rule_str + "\\")
        )
    
    def _op_matches(self, field_value: Any, rule_value: Any) -> bool:
        """
        Regex pattern match.
        
        Uses Python's re module for pattern matching.
        Pattern is case-insensitive by default.
        """
        if field_value is None or rule_value is None:
            return False
        
        try:
            return bool(re.search(
                str(rule_value),
                str(field_value),
                re.IGNORECASE
            ))
        except re.error as e:
            logger.warning("Invalid regex pattern '%s': %s", rule_value, e)
            return False
    
    def _op_is_null(self, field_value: Any, rule_value: Any) -> bool:
        """
        Check if field is null/empty.
        
        Considers None, empty string, and empty list as null.
        """
        if field_value is None:
            return True
        if isinstance(field_value, str) and field_value.strip() == "":
            return True
        if isinstance(field_value, list) and len(field_value) == 0:
            return True
        return False
    
    def _op_is_not_null(self, field_value: Any, rule_value: Any) -> bool:
        """Check if field has a value - inverse of isNull"""
        return not self._op_is_null(field_value, rule_value)
    
    def _op_gt(self, field_value: Any, rule_value: Any) -> bool:
        """Greater than comparison (numeric/date)"""
        return self._numeric_compare(field_value, rule_value, lambda a, b: a > b)
    
    def _op_lt(self, field_value: Any, rule_value: Any) -> bool:
        """Less than comparison (numeric/date)"""
        return self._numeric_compare(field_value, rule_value, lambda a, b: a < b)
    
    def _op_gte(self, field_value: Any, rule_value: Any) -> bool:
        """Greater than or equal comparison (numeric/date)"""
        return self._numeric_compare(field_value, rule_value, lambda a, b: a >= b)
    
    def _op_lte(self, field_value: Any, rule_value: Any) -> bool:
        """Less than or equal comparison (numeric/date)"""
        return self._numeric_compare(field_value, rule_value, lambda a, b: a <= b)
    
    def _evaluate_contains_any(
        self,
        rule: 'Rule',
        work_item: Dict[str, Any],
        analysis: Optional['AnalysisResult'] = None
    ) -> bool:
        """
        Multi-field, multi-keyword evaluation.
        
        Resolves each field in rule.fields, then checks if ANY resolved
        field value contains ANY of the comma-separated keywords in
        rule.value.  All comparisons are case-insensitive.
        
        Returns True on the first match (short-circuit).
        """
        # Parse keywords from the rule value (comma-separated string or list)
        if isinstance(rule.value, list):
            keywords = [k.strip().lower() for k in rule.value if k.strip()]
        elif isinstance(rule.value, str):
            keywords = [k.strip().lower() for k in rule.value.split(",") if k.strip()]
        else:
            keywords = []
        
        if not keywords:
            logger.debug("    containsAny: no keywords — returning False")
            return False
        
        fields_to_check = rule.fields if rule.fields else ([rule.field] if rule.field else [])
        if not fields_to_check:
            logger.debug("    containsAny: no fields — returning False")
            return False
        
        for field_name in fields_to_check:
            field_value = self._resolve_field(field_name, work_item, analysis)
            if field_value is None:
                continue
            
            # Normalise to a single searchable string
            if isinstance(field_value, list):
                text = " ".join(str(v) for v in field_value).lower()
            else:
                text = str(field_value).lower()
            
            for kw in keywords:
                if kw in text:
                    logger.debug(
                        "    containsAny HIT: keyword '%s' found in field '%s'",
                        kw, field_name,
                    )
                    return True
        
        logger.debug("    containsAny: no matches across %d fields", len(fields_to_check))
        return False

    def _op_contains_any(self, field_value: Any, rule_value: Any) -> bool:
        """
        Operator-handler shim for containsAny.
        
        This is only called if a containsAny rule happens to go through
        the standard _apply_operator path (shouldn't normally happen since
        evaluate_rule short-circuits).  Provided for completeness.
        """
        if field_value is None or rule_value is None:
            return False
        
        if isinstance(rule_value, list):
            keywords = [k.strip().lower() for k in rule_value if isinstance(k, str) and k.strip()]
        elif isinstance(rule_value, str):
            keywords = [k.strip().lower() for k in rule_value.split(",") if k.strip()]
        else:
            return False
        
        text = str(field_value).lower()
        return any(kw in text for kw in keywords)

    # ── regexMatchAny — multi-field, multi-pattern ─────────────
    def _evaluate_regex_match_any(
        self,
        rule: 'Rule',
        work_item: Dict[str, Any],
        analysis: Optional['AnalysisResult'] = None
    ) -> bool:
        """
        Multi-field, multi-pattern regex evaluation.

        Resolves each field in rule.fields, then checks if ANY resolved
        field value matches ANY of the comma-separated regex patterns in
        rule.value.  All comparisons are case-insensitive.

        Returns True on the first match (short-circuit).
        """
        # Parse patterns from the rule value (comma-separated string or list)
        if isinstance(rule.value, list):
            patterns = [p.strip() for p in rule.value if p.strip()]
        elif isinstance(rule.value, str):
            patterns = [p.strip() for p in rule.value.split(",") if p.strip()]
        else:
            patterns = []

        if not patterns:
            logger.debug("    regexMatchAny: no patterns — returning False")
            return False

        fields_to_check = rule.fields if rule.fields else ([rule.field] if rule.field else [])
        if not fields_to_check:
            logger.debug("    regexMatchAny: no fields — returning False")
            return False

        for field_name in fields_to_check:
            field_value = self._resolve_field(field_name, work_item, analysis)
            if field_value is None:
                continue

            # Normalise to a single searchable string
            if isinstance(field_value, list):
                text = " ".join(str(v) for v in field_value)
            else:
                text = str(field_value)

            for pattern in patterns:
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        logger.debug(
                            "    regexMatchAny HIT: pattern '%s' matched in field '%s'",
                            pattern, field_name,
                        )
                        return True
                except re.error as exc:
                    logger.warning(
                        "    regexMatchAny: invalid regex '%s' — %s",
                        pattern, exc,
                    )

        logger.debug("    regexMatchAny: no matches across %d fields", len(fields_to_check))
        return False

    def _op_regex_match_any(self, field_value: Any, rule_value: Any) -> bool:
        """
        Operator-handler shim for regexMatchAny.

        Only called if a regexMatchAny rule goes through the standard
        _apply_operator path (shouldn't normally happen since evaluate_rule
        short-circuits).  Provided for completeness.
        """
        if field_value is None or rule_value is None:
            return False

        if isinstance(rule_value, list):
            patterns = [p.strip() for p in rule_value if isinstance(p, str) and p.strip()]
        elif isinstance(rule_value, str):
            patterns = [p.strip() for p in rule_value.split(",") if p.strip()]
        else:
            return False

        text = str(field_value)
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            except re.error:
                continue
        return False

    def _numeric_compare(
        self,
        field_value: Any,
        rule_value: Any,
        comparator
    ) -> bool:
        """
        Generic numeric comparison with type coercion.
        
        Attempts to convert both values to float for comparison.
        Falls back to string comparison for date strings.
        
        Args:
            field_value: Field value to compare
            rule_value:  Rule value to compare against
            comparator:  Lambda function for the comparison
            
        Returns:
            True if the comparison holds
        """
        if field_value is None or rule_value is None:
            return False
        
        try:
            # Try numeric comparison
            return comparator(float(field_value), float(rule_value))
        except (ValueError, TypeError):
            pass
        
        try:
            # Try string comparison (works for ISO date strings)
            return comparator(str(field_value), str(rule_value))
        except (ValueError, TypeError):
            return False
