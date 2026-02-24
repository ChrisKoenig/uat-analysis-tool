"""
Triage Team Model
=================

Represents a triage team configuration. Each team has its own
ADO saved query that populates its triage queue.

Rules, Triggers, Actions, and Routes can be scoped to a specific
team or made available to all teams.

Cosmos DB Container: triage-teams
Partition Key: /status
"""

from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional

from .base import BaseEntity, EntityStatus


@dataclass
class TriageTeam(BaseEntity):
    """
    A triage team configuration.

    Attributes:
        adoQueryId:    GUID of the saved ADO query that drives this team's queue
        adoQueryName:  Human-readable name of the ADO query (informational)
        organization:  ADO organization (defaults to the read org if blank)
        project:       ADO project (defaults to the read project if blank)
        displayOrder:  Order in dropdowns (lower = first, default 100)

    Partition Key: status (active/inactive)
    """

    # -------------------------------------------------------------------------
    # Team Configuration
    # -------------------------------------------------------------------------
    adoQueryId: str = ""        # GUID of the saved ADO query
    adoQueryName: str = ""      # Human-readable query name (display only)
    organization: str = ""      # ADO organization (blank = default read org)
    project: str = ""           # ADO project (blank = default read project)
    displayOrder: int = 100     # Sort order in dropdowns

    def validate(self) -> List[str]:
        """
        Validate triage team configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = super().validate() if hasattr(super(), 'validate') else []

        if not self.name:
            errors.append("Team name is required")

        if not self.adoQueryId:
            errors.append("ADO Query ID (GUID) is required")

        if self.status not in ("active", "disabled"):
            errors.append(f"Invalid status '{self.status}'. Must be 'active' or 'disabled'")

        return errors
