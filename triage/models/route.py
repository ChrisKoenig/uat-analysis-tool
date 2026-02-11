"""
Route Model
============

Represents a collection of actions to execute when a decision tree matches.
Routes are the fourth layer of the four-layer model, grouping atomic actions
into a logical set that together produce a complete triage routing.

When a route executes, ALL of its actions are applied to the work item
in the order they appear in the actions list.

Examples:
    Route: "AI Triage Team"
        actions: ["action-1", "action-2"]
        → Sets Area Path to AI team + Assigns to AI Triage
    
    Route: "Needs Info - Missing Milestone"
        actions: ["action-3", "action-5"]
        → Posts Discussion comment + Sets Analysis.State = "Needs Info"
    
    Route: "Self-Service Redirect"
        actions: ["action-3", "action-4"]
        → Posts instructions + Closes the item

Cosmos DB Container: routes
Partition Key: /status
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Set

from .base import BaseEntity


@dataclass
class Route(BaseEntity):
    """
    A collection of actions that execute together when a tree matches.
    
    Routes are the fourth layer of the four-layer model. They group
    atomic actions into meaningful routing outcomes. When a decision
    tree evaluates to True, its Route is executed, applying all
    referenced actions to the work item.
    
    Attributes:
        actions: Ordered list of action IDs to execute. Actions are
                 applied in list order, which matters when one action
                 depends on another (e.g., set state before posting comment).
    
    Partition Key: status (active/disabled/staged)
    """
    
    # -------------------------------------------------------------------------
    # Route Definition
    # -------------------------------------------------------------------------
    actions: List[str] = field(    # Ordered list of action IDs
        default_factory=list
    )
    
    def validate(self) -> List[str]:
        """
        Validate route configuration.
        
        Checks:
            1. Base entity fields (id, name, status)
            2. At least one action is referenced
            3. No duplicate action IDs
        
        Returns:
            List of validation error strings (empty = valid)
        """
        errors = super().validate()
        
        # Must have at least one action
        if not self.actions:
            errors.append("actions list cannot be empty (need at least one action)")
        
        # Check for duplicate action references
        if len(self.actions) != len(set(self.actions)):
            seen = set()
            dupes = []
            for action_id in self.actions:
                if action_id in seen:
                    dupes.append(action_id)
                seen.add(action_id)
            errors.append(f"Duplicate action IDs: {dupes}")
        
        # Validate action IDs are non-empty strings
        for i, action_id in enumerate(self.actions):
            if not action_id or not isinstance(action_id, str):
                errors.append(
                    f"Action at index {i} must be a non-empty string ID"
                )
        
        return errors
    
    def get_referenced_action_ids(self) -> Set[str]:
        """
        Get all action IDs referenced by this route.
        
        Useful for:
            - Validating that all referenced actions exist
            - Building "used in" reference tracking
            - Detecting orphaned actions
        
        Returns:
            Set of action ID strings
        """
        return set(self.actions)
    
    def add_action(self, action_id: str) -> None:
        """
        Add an action to the end of the route's action list.
        
        Args:
            action_id: ID of the action to add
            
        Raises:
            ValueError: If action_id is already in the list
        """
        if action_id in self.actions:
            raise ValueError(
                f"Action '{action_id}' is already in this route"
            )
        self.actions.append(action_id)
    
    def remove_action(self, action_id: str) -> None:
        """
        Remove an action from the route's action list.
        
        Args:
            action_id: ID of the action to remove
            
        Raises:
            ValueError: If action_id is not in the list
        """
        if action_id not in self.actions:
            raise ValueError(
                f"Action '{action_id}' is not in this route"
            )
        self.actions.remove(action_id)
    
    def reorder_actions(self, new_order: List[str]) -> None:
        """
        Replace the action list with a new ordering.
        
        Validates that the new order contains the same actions.
        
        Args:
            new_order: List of action IDs in the desired order
            
        Raises:
            ValueError: If new_order doesn't match current actions
        """
        if set(new_order) != set(self.actions):
            raise ValueError(
                "New order must contain exactly the same action IDs. "
                f"Current: {self.actions}, New: {new_order}"
            )
        self.actions = new_order
    
    def to_display_string(self) -> str:
        """
        Human-readable representation of the route.
        
        Example: "Route 'AI Triage Team': 3 actions [action-1, action-2, action-3]"
        
        Returns:
            Formatted string describing the route
        """
        action_list = ", ".join(self.actions) if self.actions else "(none)"
        return (
            f"Route '{self.name}': {len(self.actions)} actions "
            f"[{action_list}]"
        )
    
    def __repr__(self) -> str:
        return (
            f"Route(id='{self.id}', name='{self.name}', "
            f"actions={len(self.actions)}, status='{self.status}')"
        )
