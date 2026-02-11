"""
Routes Engine
=============

Executes a route by applying all its actions to a work item.
This is Layer 3+4 of the four-layer model - routes resolve action
references and apply them in order.

The routes engine does NOT directly update ADO. Instead, it:
    1. Resolves the route's action IDs to Action objects
    2. For each action, computes the field change (field, operation, value)
    3. Returns a list of planned field changes
    4. The caller (evaluation service) applies changes to ADO

This separation keeps the engine testable and allows dry-run mode
(compute what would change without writing to ADO).

Template Resolution:
    Template actions contain variables like {CreatedBy}, {WorkItemId}, etc.
    These are resolved against the work item data and analysis results
    before the changes are returned.

Action Operations:
    set:          Static value assignment
    set_computed: Computed value (today(), currentUser())
    copy:         Copy value from another field
    append:       Append to existing value
    template:     Variable substitution in a template string
"""

import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

from ..models.action import Action
from ..models.route import Route
from ..models.analysis_result import AnalysisResult

logger = logging.getLogger("triage.engines.routes")


class FieldChange:
    """
    Represents a single planned field change.
    
    Captures the field to change, the operation, the computed new value,
    and the current (old) value for audit tracking.
    
    Attributes:
        field:     ADO field reference name
        operation: How the value was determined (set, copy, template, etc.)
        old_value: Current field value (for audit {from, to})
        new_value: Computed new value to apply
        action_id: ID of the action that produced this change
    """
    
    def __init__(
        self,
        field: str,
        operation: str,
        old_value: Any,
        new_value: Any,
        action_id: str
    ):
        self.field = field
        self.operation = operation
        self.old_value = old_value
        self.new_value = new_value
        self.action_id = action_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for storage/serialization"""
        return {
            "field": self.field,
            "operation": self.operation,
            "from": self.old_value,
            "to": self.new_value,
            "actionId": self.action_id,
        }
    
    def __repr__(self) -> str:
        return (
            f"FieldChange({self.field}: "
            f"'{self.old_value}' → '{self.new_value}' "
            f"[{self.operation}])"
        )


class RoutesEngine:
    """
    Resolves and computes field changes for a route's actions.
    
    Usage:
        engine = RoutesEngine()
        
        # Compute all field changes for a route
        changes, errors = engine.compute_changes(
            route=matched_route,
            actions=all_actions_dict,
            work_item=work_item_data,
            analysis=analysis_result,
            current_user="brad.price@microsoft.com"
        )
        
        # changes = [FieldChange(...), FieldChange(...), ...]
        # errors = []  (or list of error messages)
    """
    
    def compute_changes(
        self,
        route: Route,
        actions: Dict[str, Action],
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult] = None,
        current_user: str = "system"
    ) -> Tuple[List[FieldChange], List[str]]:
        """
        Compute all field changes for a route without writing to ADO.
        
        Resolves each action ID in the route to its Action definition,
        then computes the resulting field change based on the operation type.
        
        Args:
            route:        The route to execute
            actions:      Dict of all actions keyed by ID
            work_item:    Current work item data (for template vars, copy source)
            analysis:     Analysis result (for Analysis.* template vars)
            current_user: Email of the user triggering the evaluation
            
        Returns:
            Tuple of:
                - List[FieldChange]: Computed field changes in execution order
                - List[str]: Error messages for actions that failed
        """
        changes: List[FieldChange] = []
        errors: List[str] = []
        
        logger.info(
            "compute_changes: route '%s' with %d actions",
            route.id, len(route.actions),
        )
        
        for action_id in route.actions:
            # Resolve action ID to Action object
            action = actions.get(action_id)
            if action is None:
                logger.warning(
                    "  action '%s' NOT FOUND (referenced by route '%s')",
                    action_id, route.id,
                )
                errors.append(
                    f"Route '{route.id}' references action '{action_id}' "
                    f"which does not exist"
                )
                continue
            
            # Skip disabled actions
            if action.status != "active":
                logger.debug(
                    "  action '%s' SKIPPED (status=%s)", action_id, action.status,
                )
                errors.append(
                    f"Action '{action_id}' is {action.status}, skipping"
                )
                continue
            
            try:
                change = self._compute_single_change(
                    action, work_item, analysis, current_user
                )
                logger.debug(
                    "  action '%s' → %s(%s) = %r",
                    action_id, action.operation, action.field, change.new_value,
                )
                changes.append(change)
            except Exception as e:
                logger.error(
                    "  action '%s' ERROR: %s", action_id, e, exc_info=True,
                )
                errors.append(
                    f"Error computing action '{action_id}': {e}"
                )
        
        logger.info(
            "compute_changes complete: %d changes, %d errors",
            len(changes), len(errors),
        )
        return changes, errors
        
        return changes, errors
    
    def _compute_single_change(
        self,
        action: Action,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult],
        current_user: str
    ) -> FieldChange:
        """
        Compute the field change for a single action.
        
        Dispatches to the appropriate handler based on operation type.
        
        Args:
            action:       The action to compute
            work_item:    Current work item data
            analysis:     Analysis result
            current_user: Current user email
            
        Returns:
            FieldChange with computed values
        """
        # Get the current value of the target field (for audit tracking)
        old_value = work_item.get(action.field)
        
        # Compute the new value based on operation type
        operation_handlers = {
            "set": self._op_set,
            "set_computed": self._op_set_computed,
            "copy": self._op_copy,
            "append": self._op_append,
            "template": self._op_template,
        }
        
        handler = operation_handlers.get(action.operation)
        if handler is None:
            raise ValueError(
                f"Unknown operation: '{action.operation}'"
            )
        
        new_value = handler(
            action, work_item, analysis, current_user
        )
        
        return FieldChange(
            field=action.field,
            operation=action.operation,
            old_value=old_value,
            new_value=new_value,
            action_id=action.id,
        )
    
    # =========================================================================
    # Operation Handlers
    # =========================================================================
    
    def _op_set(
        self,
        action: Action,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult],
        current_user: str
    ) -> Any:
        """
        Set operation: return the static value as-is.
        
        Example: SET System.AreaPath = "UAT\\MCAPS\\AI"
        """
        return action.value
    
    def _op_set_computed(
        self,
        action: Action,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult],
        current_user: str
    ) -> Any:
        """
        Set computed value from a known function.
        
        Supported functions:
            today()       → Current date in ISO 8601 format
            currentUser() → The user who triggered the evaluation
        """
        computed_functions = {
            "today()": lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "currentUser()": lambda: current_user,
        }
        
        func = computed_functions.get(action.value)
        if func is None:
            raise ValueError(
                f"Unknown computed function: '{action.value}'"
            )
        
        return func()
    
    def _op_copy(
        self,
        action: Action,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult],
        current_user: str
    ) -> Any:
        """
        Copy value from another field.
        
        The action.value contains the source field name.
        
        Example: COPY System.AssignedTo FROM System.CreatedBy
        """
        source_field = action.value
        
        # Try work item fields first
        if source_field in work_item:
            return work_item[source_field]
        
        # Try analysis fields
        if source_field.startswith("Analysis.") and analysis:
            analysis_field = source_field[len("Analysis."):]
            return analysis.get_analysis_field(analysis_field)
        
        # Source field not found
        return None
    
    def _op_append(
        self,
        action: Action,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult],
        current_user: str
    ) -> Any:
        """
        Append to existing field value.
        
        For strings: concatenate with separator
        For lists: add to the list
        For None: just set the value
        
        Example: APPEND Tags += "Triaged"
        """
        current = work_item.get(action.field)
        append_value = action.value
        
        if current is None:
            # No existing value - just set
            return append_value
        
        if isinstance(current, list):
            # Append to list
            if isinstance(append_value, list):
                return current + append_value
            else:
                return current + [append_value]
        
        if isinstance(current, str):
            # Append to string with separator
            # For tags, use semicolons. For other fields, use newline.
            if "tag" in action.field.lower():
                separator = "; "
            else:
                separator = "\n"
            return f"{current}{separator}{append_value}"
        
        # Fallback: convert to string and concatenate
        return f"{current} {append_value}"
    
    def _op_template(
        self,
        action: Action,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult],
        current_user: str
    ) -> str:
        """
        Variable substitution in a template string.
        
        Replaces {variable} placeholders with actual values from
        the work item and analysis data.
        
        Supported variables:
            {CreatedBy}           → Work item creator
            {WorkItemId}          → Work item ID
            {Title}               → Work item title
            {today()}             → Current date
            {currentUser()}       → Authenticated user
            {Analysis.Category}   → Analysis category
            {Analysis.Products}   → Detected products (comma-separated)
        
        Example:
            Template: "@{CreatedBy} - Please provide the Milestone ID for {Title}"
            Result:   "@john.doe@ms.com - Please provide the Milestone ID for GPU Request"
        """
        template = str(action.value)
        
        # Build the variable resolution map
        variables = {
            "{CreatedBy}": work_item.get("System.CreatedBy", ""),
            "{WorkItemId}": str(work_item.get("System.Id", "")),
            "{Title}": work_item.get("System.Title", 
                       work_item.get("Title", "")),
            "{today()}": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "{currentUser()}": current_user,
        }
        
        # Add Analysis.* variables if analysis is available
        if analysis:
            variables["{Analysis.Category}"] = analysis.category or ""
            products = analysis.detectedProducts or []
            variables["{Analysis.Products}"] = ", ".join(products)
            variables["{Analysis.Confidence}"] = str(analysis.confidence)
            variables["{Analysis.Intent}"] = analysis.intent or ""
            variables["{Analysis.ContextSummary}"] = (
                analysis.contextSummary or ""
            )
        
        # Replace all known variables
        result = template
        for var, value in variables.items():
            result = result.replace(var, str(value))
        
        # Warn about unresolved variables (but don't fail)
        unresolved = re.findall(r'\{[^}]+\}', result)
        if unresolved:
            logger.warning(
                "Unresolved template variables in action '%s': %s",
                action.id, unresolved,
            )
        
        return result
    
    def preview_changes(
        self,
        route: Route,
        actions: Dict[str, Action]
    ) -> List[Dict[str, str]]:
        """
        Preview what a route would do without actual work item data.
        
        Returns action descriptions suitable for the admin UI preview.
        Does not resolve templates or copy sources.
        
        Args:
            route:   Route to preview
            actions: All actions dict
            
        Returns:
            List of action descriptions
        """
        preview = []
        for action_id in route.actions:
            action = actions.get(action_id)
            if action:
                preview.append({
                    "actionId": action.id,
                    "actionName": action.name,
                    "description": action.to_display_string(),
                    "status": action.status,
                })
            else:
                preview.append({
                    "actionId": action_id,
                    "actionName": "(missing)",
                    "description": f"Action '{action_id}' not found",
                    "status": "error",
                })
        return preview
