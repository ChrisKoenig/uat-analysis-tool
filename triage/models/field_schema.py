"""
Field Schema Model
==================

Represents the definition and metadata for an ADO work item field.
Combines ADO-native field metadata (type, allowed values, required)
with custom enrichment (valid operators, display grouping, evaluate/set flags).

Field schema is initially loaded from the ADO REST API:
    GET .../_apis/wit/workitemtypes/{type}/fields?$expand=All&api-version=7.1

Then enriched by admins through the UI:
    - Which operators are valid for this field
    - Whether the field can be evaluated (read) and/or set (write)
    - Display group for UI organization

Cosmos DB Container: field-schema
Partition Key: /source
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any

from .base import utc_now


@dataclass
class FieldSchema:
    """
    Definition and metadata for a single ADO work item field.
    
    Combines two data sources:
        1. ADO API: type, allowedValues, required, readOnly
        2. Custom enrichment: operators, canEvaluate, canSet, group
    
    Not a BaseEntity - field schemas don't have active/disabled lifecycle,
    but they do have a source partition key.
    
    Attributes:
        id:            ADO field reference name (e.g., "System.AreaPath")
        displayName:   Human-friendly name (e.g., "Area Path")
        type:          Field data type (string, integer, treePath, html, etc.)
        source:        Where this field comes from ("ado", "analysis", "system")
        canEvaluate:   Can this field be used in rule conditions?
        canSet:        Can this field be written by actions?
        operators:     List of valid operators for this field
        allowedValues: Constrained values if applicable
        required:      Is this field required by ADO?
        readOnly:      Is this field read-only in ADO?
        group:         Display group in admin UI (e.g., "Standard", "Custom", "Analysis")
        description:   Additional notes about the field
    """
    
    # -------------------------------------------------------------------------
    # Identity (from ADO)
    # -------------------------------------------------------------------------
    id: str = ""                              # ADO reference name
    displayName: str = ""                     # Human name
    type: str = "string"                      # Data type
    source: str = "ado"                       # ado | analysis | system
    
    # -------------------------------------------------------------------------
    # Capabilities (custom enrichment)
    # -------------------------------------------------------------------------
    canEvaluate: bool = False                 # Can be used in rules
    canSet: bool = False                      # Can be modified by actions
    operators: List[str] = field(             # Valid operators
        default_factory=list
    )
    
    # -------------------------------------------------------------------------
    # ADO Metadata
    # -------------------------------------------------------------------------
    allowedValues: List[str] = field(         # Constrained values
        default_factory=list
    )
    required: bool = False                    # Required by ADO
    readOnly: bool = False                    # Read-only in ADO
    
    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------
    group: str = "Standard"                   # UI display group
    description: str = ""                     # Additional notes
    
    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    lastSynced: str = field(default_factory=utc_now)  # Last ADO sync time
    modifiedBy: str = ""                      # Last enrichment editor
    modifiedDate: str = field(default_factory=utc_now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Cosmos DB storage"""
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FieldSchema':
        """Create from Cosmos DB document"""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    def supports_operator(self, operator: str) -> bool:
        """Check if this field supports the given operator"""
        return operator in self.operators
    
    def get_default_operators(self) -> List[str]:
        """
        Get default operators based on field type.
        
        Used when first importing a field from ADO - provides
        sensible defaults that admins can then customize.
        
        Returns:
            List of operator strings appropriate for the field type
        """
        # Universal operators
        base = ["equals", "notEquals", "isNull", "isNotNull"]
        
        type_operators = {
            "string": base + ["contains", "notContains", "startsWith",
                             "matches", "in", "notIn"],
            "plainText": base + ["contains", "notContains", "startsWith",
                                "matches"],
            "html": base + ["contains", "notContains"],
            "treePath": base + ["under", "startsWith"],
            "integer": base + ["gt", "lt", "gte", "lte", "in", "notIn"],
            "double": base + ["gt", "lt", "gte", "lte"],
            "dateTime": base + ["gt", "lt", "gte", "lte"],
            "boolean": ["equals", "notEquals"],
            "identity": base + ["in", "notIn"],
        }
        
        return type_operators.get(self.type, base)
    
    def __repr__(self) -> str:
        caps = []
        if self.canEvaluate:
            caps.append("eval")
        if self.canSet:
            caps.append("set")
        caps_str = "+".join(caps) if caps else "none"
        return (
            f"FieldSchema(id='{self.id}', type='{self.type}', "
            f"caps={caps_str}, operators={len(self.operators)})"
        )
