"""
Evaluation Model
================

Represents the result of evaluating a single work item through the
triage pipeline. Captures all rule results (T/F), the matched tree,
applied route, executed actions, and field changes.

This is the core audit record for every evaluation, stored in the
evaluations container with workItemId as the partition key.

Each evaluation is a snapshot in time - re-evaluating the same work item
creates a new evaluation record, preserving full history.

Cosmos DB Container: evaluations
Partition Key: /workItemId
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .base import utc_now


# =============================================================================
# Analysis State Values
# =============================================================================
# These match the Custom.ROBAnalysisState field values in ADO.

class AnalysisState:
    """
    Analysis.State lifecycle values.
    
    Terminal states: Approved, Override
    Non-terminal: everything else (can be re-evaluated)
    """
    PENDING = "Pending"
    AWAITING_APPROVAL = "Awaiting Approval"
    NEEDS_INFO = "Needs Info"
    REDIRECTED = "Redirected"
    NO_MATCH = "No Match"
    APPROVED = "Approved"
    OVERRIDE = "Override"
    ERROR = "Error"
    
    # States that indicate processing is complete
    TERMINAL_STATES = {APPROVED, OVERRIDE}
    
    # States that allow re-evaluation
    RETRIGGERABLE_STATES = {PENDING, NEEDS_INFO, NO_MATCH, ERROR}
    
    @classmethod
    def is_terminal(cls, state: str) -> bool:
        """Check if a state is terminal (no further processing)"""
        return state in cls.TERMINAL_STATES
    
    @classmethod
    def allows_retrigger(cls, state: str) -> bool:
        """Check if a state allows re-evaluation"""
        return state in cls.RETRIGGERABLE_STATES


@dataclass
class Evaluation:
    """
    Result of evaluating a single work item through the triage pipeline.
    
    Captures the complete evaluation lifecycle:
        1. All rule evaluations (T/F per rule)
        2. Skipped rules (disabled or errors)
        3. The matched decision tree (if any)
        4. The applied route and executed actions
        5. Field changes made to the work item
        6. The resulting Analysis.State
    
    Not a BaseEntity - evaluations are immutable records, not managed
    entities. They have no status/version lifecycle.
    
    Attributes:
        id:               Unique evaluation ID (eval-{workItemId}-{timestamp})
        workItemId:       ADO work item ID (partition key)
        date:             Evaluation timestamp
        evaluatedBy:      "system" or user email (for manual trigger)
        ruleResults:      Dict of rule ID → True/False
        skippedRules:     Rules not evaluated (disabled, error)
        matchedTree:      ID of the first tree that matched (or None)
        appliedRoute:     ID of the route that was executed (or None)
        actionsExecuted:  List of action IDs that were applied
        analysisState:    Resulting Analysis.State value
        summaryHtml:      HTML summary for ADO Challenge Details field
        fieldsChanged:    Dict of field → {from, to} for each change
        errors:           Any errors encountered during evaluation
        isDryRun:         True if this was a test run (no ADO updates)
    """
    
    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------
    id: str = ""                              # eval-{workItemId}-{timestamp}
    workItemId: int = 0                       # ADO work item ID (partition key)
    date: str = field(default_factory=utc_now)  # Evaluation timestamp
    evaluatedBy: str = "system"               # Who triggered the evaluation
    
    # -------------------------------------------------------------------------
    # Rule Results
    # -------------------------------------------------------------------------
    ruleResults: Dict[str, bool] = field(     # rule ID → True/False
        default_factory=dict
    )
    skippedRules: List[str] = field(          # Rule IDs that were skipped
        default_factory=list
    )
    
    # -------------------------------------------------------------------------
    # Routing Results
    # -------------------------------------------------------------------------
    matchedTree: Optional[str] = None         # Tree ID that matched (or None)
    appliedRoute: Optional[str] = None        # Route ID executed (or None)
    actionsExecuted: List[str] = field(       # Action IDs applied
        default_factory=list
    )
    analysisState: str = AnalysisState.PENDING  # Resulting state
    
    # -------------------------------------------------------------------------
    # Output
    # -------------------------------------------------------------------------
    summaryHtml: str = ""                     # HTML for Challenge Details
    fieldsChanged: Dict[str, Dict] = field(   # field → {from, to}
        default_factory=dict
    )
    
    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    errors: List[str] = field(                # Errors during evaluation
        default_factory=list
    )
    isDryRun: bool = False                    # True = test mode, no ADO writes
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert evaluation to a dictionary for Cosmos DB storage.
        
        Returns:
            Dict with all evaluation fields
        """
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Evaluation':
        """
        Create an Evaluation from a Cosmos DB document.
        
        Args:
            data: Dict from Cosmos DB
            
        Returns:
            New Evaluation instance
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    def had_match(self) -> bool:
        """Check if any decision tree matched"""
        return self.matchedTree is not None
    
    def had_errors(self) -> bool:
        """Check if any errors occurred"""
        return len(self.errors) > 0
    
    def rules_evaluated_count(self) -> int:
        """Number of rules that were actually evaluated"""
        return len(self.ruleResults)
    
    def rules_matched_count(self) -> int:
        """Number of rules that evaluated to True"""
        return sum(1 for v in self.ruleResults.values() if v)
    
    def generate_id(self) -> str:
        """
        Generate a unique evaluation ID from workItemId and timestamp.
        
        Format: eval-{workItemId}-{YYYYMMDDHHmmss}
        
        Returns:
            Generated ID string
        """
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        self.id = f"eval-{self.workItemId}-{ts}"
        return self.id
    
    def __repr__(self) -> str:
        match_info = f"→ {self.matchedTree}" if self.matchedTree else "no match"
        return (
            f"Evaluation(workItem={self.workItemId}, "
            f"rules={self.rules_evaluated_count()}/{self.rules_matched_count()} T, "
            f"{match_info}, state='{self.analysisState}')"
        )
