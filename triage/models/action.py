"""
Action Model
=============

Represents an atomic field assignment in the triage system.
An action defines a single change to apply to an ADO work item
when a route is executed.

Operations:
    set:          Set a field to a static value
    set_computed: Set a field to a computed value (e.g., today())
    copy:         Copy value from another field
    append:       Append to an existing field value
    template:     Set with variable substitution (e.g., @{CreatedBy})

Examples:
    Action: "Set Area Path to AI"
        field: "System.AreaPath"
        operation: "set"
        value: "UAT\\MCAPS\\AI"
    
    Action: "Ping submitter for missing data"
        field: "Discussion"
        operation: "template"
        value: "@{CreatedBy} - Please provide the Milestone ID..."

Cosmos DB Container: actions
Partition Key: /status
"""

from dataclasses import dataclass
from typing import Any, List, Dict, Optional

from .base import BaseEntity


# =============================================================================
# Supported Operations
# =============================================================================

VALID_OPERATIONS = [
    "set",           # Set field to a static value
    "set_computed",  # Set field to a computed value (today(), currentUser())
    "copy",          # Copy value from another field
    "append",        # Append to existing value
    "template",      # Set with variable substitution ({CreatedBy}, etc.)
]

# Recognized template variables for the 'template' operation
TEMPLATE_VARIABLES = [
    "{CreatedBy}",
    "{WorkItemId}",
    "{Title}",
    "{today()}",
    "{currentUser()}",
    "{Analysis.Category}",
    "{Analysis.Products}",
    "{Analysis.Confidence}",
    "{Analysis.Intent}",
    "{Analysis.ContextSummary}",
]


@dataclass
class Action(BaseEntity):
    """
    An atomic action that sets a single field on an ADO work item.
    
    Actions are the smallest unit of work item modification. They are
    grouped into Routes and executed together when a decision tree matches.
    
    Attributes:
        field:      ADO field to modify (e.g., "System.AreaPath")
        operation:  Type of modification (set, set_computed, copy, append, template)
        value:      The value to set/apply:
                    - For "set": the literal value
                    - For "set_computed": the function name (e.g., "today()")
                    - For "copy": the source field name
                    - For "append": the text to append
                    - For "template": the template string with {variables}
        valueType:  Hint for the value type: "static", "computed", "field_ref", "template"
        
    Partition Key: status (active/disabled/staged)
    """
    
    # -------------------------------------------------------------------------
    # Action Definition
    # -------------------------------------------------------------------------
    field: str = ""            # ADO field to modify
    operation: str = ""        # Operation type (see VALID_OPERATIONS)
    value: Any = None          # Value to set (type depends on operation)
    valueType: str = "static"  # Value type hint for the UI
    
    def validate(self) -> List[str]:
        """
        Validate action configuration.
        
        Checks:
            1. Base entity fields (id, name, status)
            2. Target field is specified
            3. Operation is from the supported list
            4. Value is appropriate for the operation
        
        Returns:
            List of validation error strings (empty = valid)
        """
        errors = super().validate()
        
        # Field to modify is required
        if not self.field:
            errors.append("field is required (the ADO field to modify)")
        
        # Operation must be from the known list
        if not self.operation:
            errors.append("operation is required")
        elif self.operation not in VALID_OPERATIONS:
            errors.append(
                f"Unknown operation '{self.operation}'. "
                f"Valid operations: {VALID_OPERATIONS}"
            )
        
        # Value is required for all operations
        if self.value is None and self.operation:
            errors.append(
                f"value is required for operation '{self.operation}'"
            )
        
        # Operation-specific validation
        if self.operation == "copy" and self.value:
            # Copy value should be a field reference
            if not isinstance(self.value, str):
                errors.append(
                    "For 'copy' operation, value must be a field name string"
                )
        
        if self.operation == "set_computed" and self.value:
            # Computed values should be known functions
            known_functions = ["today()", "currentUser()"]
            if self.value not in known_functions:
                errors.append(
                    f"Unknown computed function '{self.value}'. "
                    f"Known functions: {known_functions}"
                )
        
        return errors
    
    def to_display_string(self) -> str:
        """
        Human-readable representation of the action.
        
        Examples:
            "SET System.AreaPath = 'UAT\\MCAPS\\AI'"
            "COPY System.AssignedTo FROM System.CreatedBy"
            "APPEND Discussion += '...'"
            "TEMPLATE Discussion = '@{CreatedBy} - Please provide...'"
        
        Returns:
            Formatted string describing the action
        """
        if self.operation == "copy":
            return f"COPY {self.field} FROM {self.value}"
        elif self.operation == "append":
            display_val = str(self.value)[:60]
            return f"APPEND {self.field} += '{display_val}'"
        elif self.operation == "template":
            display_val = str(self.value)[:60]
            return f"TEMPLATE {self.field} = '{display_val}'"
        elif self.operation == "set_computed":
            return f"SET {self.field} = {self.value}"
        else:
            # Default: set
            return f"SET {self.field} = '{self.value}'"
    
    def __repr__(self) -> str:
        return (
            f"Action(id='{self.id}', name='{self.name}', "
            f"action='{self.to_display_string()}', "
            f"status='{self.status}')"
        )
