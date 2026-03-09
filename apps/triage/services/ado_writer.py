"""
ADO Writer Service
==================

High-level service that applies triage evaluation results to ADO work items.
Orchestrates the ADO client to write field changes, post discussion comments,
and manage the Analysis State field.

This service sits between the evaluation pipeline and the ADO REST client,
providing:
    - Smart field change application (skip no-ops, handle special fields)
    - Discussion comment posting with @mention formatting
    - Analysis State lifecycle management
    - HTML summary injection into Challenge Details field
    - Conflict detection and retry logic
    - Audit logging of all ADO writes

Pipeline Integration:
    EvaluationService.evaluate() → Evaluation result
                                        ↓
    AdoWriterService.apply()     → Writes to ADO
                                        ↓
    AuditService.log_change()    → Audit trail

Usage:
    writer = AdoWriterService()
    
    # Apply an evaluation's computed changes to ADO
    result = writer.apply_evaluation(evaluation, revision=5)
    
    # Or apply individual field changes
    result = writer.apply_field_changes(12345, field_changes, revision=5)
    
    # Post a discussion comment
    result = writer.post_discussion_comment(12345, html_content)
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
import logging

from .ado_client import AdoClient, get_ado_client
from ..engines.routes_engine import FieldChange
from ..models.evaluation import Evaluation, AnalysisState

logger = logging.getLogger("triage.services.ado_write")


class AdoWriteResult:
    """
    Result of an ADO write operation.
    
    Captures success/failure, what was written, and any errors
    encountered during the write.
    
    Attributes:
        success:          True if all writes completed
        work_item_id:     ADO work item ID
        fields_updated:   Number of fields successfully changed
        comment_posted:   Whether a discussion comment was posted
        new_revision:     ADO revision after update (for conflict tracking)
        conflict:         True if a 409 Conflict was returned
        errors:           List of error messages
    """
    
    def __init__(self, work_item_id: int):
        self.success = False
        self.work_item_id = work_item_id
        self.fields_updated = 0
        self.comment_posted = False
        self.new_revision: Optional[int] = None
        self.conflict = False
        self.errors: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response"""
        return {
            "success": self.success,
            "workItemId": self.work_item_id,
            "fieldsUpdated": self.fields_updated,
            "commentPosted": self.comment_posted,
            "newRevision": self.new_revision,
            "conflict": self.conflict,
            "errors": self.errors,
        }


class AdoWriterService:
    """
    Writes triage evaluation results to Azure DevOps work items.
    
    Handles the complete write pipeline:
        1. Separate field changes from discussion comments
        2. Apply field changes via JSON Patch
        3. Post discussion comments via Comments API
        4. Update Analysis State (ROBAnalysisState)
        5. Inject HTML summary into Challenge Details
        6. Handle 409 Conflicts with retry guidance
    
    Special Field Handling:
        - Discussion:           Posted via Comments API (not a field update)
        - Custom.ROBAnalysisState: Always set as part of the update
        - Custom.pChallengeDetails: Receives the HTML evaluation summary
    
    Thread Safety:
        Uses the shared ADO client singleton. Write operations are not
        batched across work items (each item is an independent transaction).
    """
    
    # Fields that use the Comments API instead of field updates
    COMMENT_FIELDS = {"Discussion", "System.History"}
    
    # The field where we store the evaluation summary HTML
    CHALLENGE_DETAILS_FIELD = "Custom.pChallengeDetails"
    
    # The field tracking triage analysis state
    ANALYSIS_STATE_FIELD = "Custom.ROBAnalysisState"
    
    def __init__(self, ado_client: Optional[AdoClient] = None):
        """
        Initialize the writer service.
        
        Args:
            ado_client: Optional ADO client override (for testing).
                        Default: uses the shared singleton.
        """
        self._ado = ado_client or get_ado_client()
    
    def apply_evaluation(
        self,
        evaluation: Evaluation,
        revision: Optional[int] = None
    ) -> AdoWriteResult:
        """
        Apply a complete evaluation's results to ADO.
        
        This is the primary method. Takes an Evaluation object (as returned
        by EvaluationService.evaluate()) and writes everything to ADO:
            - Field changes computed by the routes engine
            - Analysis State update
            - HTML summary into Challenge Details
            - Discussion comments (for @ping / Needs Info)
        
        Args:
            evaluation:  Evaluation result to apply
            revision:    Expected work item revision for conflict detection.
                         If None, no conflict check is performed.
        
        Returns:
            AdoWriteResult with success/failure details
        """
        result = AdoWriteResult(evaluation.workItemId)
        
        # Skip dry runs — should never reach here, but safety check
        if evaluation.isDryRun:
            result.errors.append("Cannot apply a dry-run evaluation")
            return result
        
        # ================================================================
        # Step 1: Build field changes from evaluation data
        # ================================================================
        field_changes, comments = self._separate_changes(evaluation)
        
        # Always include the Analysis State update
        field_changes.append(
            FieldChange(
                field=self.ANALYSIS_STATE_FIELD,
                operation="set",
                old_value=None,
                new_value=evaluation.analysisState,
                action_id="system:analysis_state",
            )
        )
        
        # Include the HTML summary in Challenge Details
        if evaluation.summaryHtml:
            field_changes.append(
                FieldChange(
                    field=self.CHALLENGE_DETAILS_FIELD,
                    operation="set",
                    old_value=None,
                    new_value=evaluation.summaryHtml,
                    action_id="system:challenge_details",
                )
            )
        
        # ================================================================
        # Step 2: Apply field changes via PATCH
        # ================================================================
        if field_changes:
            update_result = self._ado.update_work_item(
                evaluation.workItemId,
                field_changes,
                revision=revision,
            )
            
            if update_result["success"]:
                result.fields_updated = len(field_changes)
                result.new_revision = update_result.get("rev")
            elif update_result.get("conflict"):
                result.conflict = True
                result.errors.append(update_result.get("error", "Conflict"))
                # Don't proceed with comments if field update conflicted
                return result
            else:
                result.errors.append(
                    update_result.get("error", "Field update failed")
                )
                # Continue to try comments even if field update failed
        
        # ================================================================
        # Step 3: Post discussion comments
        # ================================================================
        for comment_html in comments:
            comment_result = self._ado.add_comment(
                evaluation.workItemId, comment_html
            )
            if comment_result.get("success"):
                result.comment_posted = True
            else:
                result.errors.append(
                    f"Comment failed: {comment_result.get('error', 'Unknown')}"
                )
        
        # ================================================================
        # Step 4: Determine overall success
        # ================================================================
        # Success = field update succeeded (or no fields to update)
        # Comments are best-effort (failure logged but not fatal)
        result.success = (
            result.fields_updated > 0 or not field_changes
        ) and not result.conflict
        
        # Log
        status = "SUCCESS" if result.success else "FAILED"
        logger.info(
            "apply_evaluation %s: item=%d, fields=%d, comment=%s, state=%s",
            status, evaluation.workItemId,
            result.fields_updated,
            "yes" if result.comment_posted else "no",
            evaluation.analysisState,
        )
        
        return result
    
    def apply_field_changes(
        self,
        work_item_id: int,
        field_changes: List[FieldChange],
        revision: Optional[int] = None
    ) -> AdoWriteResult:
        """
        Apply a list of field changes directly to an ADO work item.
        
        Lower-level method for when you have FieldChange objects but
        not a full Evaluation. Separates discussion comments from
        field updates automatically.
        
        Args:
            work_item_id:  ADO work item ID
            field_changes: List of FieldChange objects to apply
            revision:      Optional revision for conflict detection
            
        Returns:
            AdoWriteResult
        """
        result = AdoWriteResult(work_item_id)
        
        # Separate comments from field updates
        updates = []
        comments = []
        
        for change in field_changes:
            if change.field in self.COMMENT_FIELDS:
                if change.new_value:
                    comments.append(str(change.new_value))
            else:
                updates.append(change)
        
        # Apply field updates
        if updates:
            update_result = self._ado.update_work_item(
                work_item_id, updates, revision=revision
            )
            
            if update_result["success"]:
                result.fields_updated = len(updates)
                result.new_revision = update_result.get("rev")
            elif update_result.get("conflict"):
                result.conflict = True
                result.errors.append(update_result.get("error", "Conflict"))
                return result
            else:
                result.errors.append(
                    update_result.get("error", "Update failed")
                )
        
        # Post comments
        for comment_html in comments:
            comment_result = self._ado.add_comment(work_item_id, comment_html)
            if comment_result.get("success"):
                result.comment_posted = True
            else:
                result.errors.append(
                    f"Comment failed: {comment_result.get('error', 'Unknown')}"
                )
        
        result.success = (
            result.fields_updated > 0 or not updates
        ) and not result.conflict
        
        return result
    
    def post_discussion_comment(
        self,
        work_item_id: int,
        html_content: str
    ) -> AdoWriteResult:
        """
        Post a standalone discussion comment on a work item.
        
        Convenience method for posting comments without field changes.
        Used for:
            - @ping notifications (Needs Info state)
            - Manual triage notes
            - Override explanations
        
        Args:
            work_item_id:  ADO work item ID
            html_content:  HTML-formatted comment body
            
        Returns:
            AdoWriteResult
        """
        result = AdoWriteResult(work_item_id)
        
        comment_result = self._ado.add_comment(work_item_id, html_content)
        
        if comment_result.get("success"):
            result.success = True
            result.comment_posted = True
        else:
            result.errors.append(
                comment_result.get("error", "Comment failed")
            )
        
        return result
    
    def update_analysis_state(
        self,
        work_item_id: int,
        new_state: str,
        revision: Optional[int] = None
    ) -> AdoWriteResult:
        """
        Update the ROBAnalysisState field on a work item.
        
        Convenience method for state transitions. Used by:
            - Webhook processor (set to "Pending" on new items)
            - Approval endpoint (set to "Approved")
            - Override endpoint (set to "Override")
        
        Args:
            work_item_id: ADO work item ID
            new_state:    Target analysis state
            revision:     Optional revision for conflict detection
            
        Returns:
            AdoWriteResult
        """
        result = AdoWriteResult(work_item_id)
        
        set_result = self._ado.set_analysis_state(
            work_item_id, new_state, revision=revision
        )
        
        if set_result["success"]:
            result.success = True
            result.fields_updated = 1
            result.new_revision = set_result.get("rev")
        elif set_result.get("conflict"):
            result.conflict = True
            result.errors.append(set_result.get("error", "Conflict"))
        else:
            result.errors.append(
                set_result.get("error", "State update failed")
            )
        
        return result
    
    # =========================================================================
    # Internal Helpers
    # =========================================================================
    
    def _separate_changes(
        self,
        evaluation: Evaluation
    ) -> Tuple[List[FieldChange], List[str]]:
        """
        Separate an evaluation's field changes into updates and comments.
        
        Extracts change data from the evaluation's fieldsChanged dict
        and creates FieldChange objects for updates, while collecting
        discussion/history content as HTML strings.
        
        Args:
            evaluation: Evaluation with fieldsChanged dict
            
        Returns:
            Tuple of (field_changes, comment_htmls)
        """
        field_changes = []
        comments = []
        
        for field, change_data in evaluation.fieldsChanged.items():
            new_value = change_data.get("to")
            old_value = change_data.get("from")
            
            if field in self.COMMENT_FIELDS:
                # Discussion changes become comments
                if new_value:
                    comments.append(str(new_value))
            else:
                # Regular field changes
                field_changes.append(
                    FieldChange(
                        field=field,
                        operation="set",  # Stored changes are always "set"
                        old_value=old_value,
                        new_value=new_value,
                        action_id="evaluation",
                    )
                )
        
        return field_changes, comments


# =============================================================================
# Singleton Access
# =============================================================================

_writer_instance: Optional[AdoWriterService] = None


def get_ado_writer() -> AdoWriterService:
    """
    Get the shared ADO writer singleton.
    
    Returns:
        AdoWriterService instance
    """
    global _writer_instance
    if _writer_instance is None:
        _writer_instance = AdoWriterService()
    return _writer_instance


def reset_ado_writer() -> None:
    """Reset the singleton (for testing)"""
    global _writer_instance
    _writer_instance = None
