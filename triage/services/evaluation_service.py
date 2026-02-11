"""
Evaluation Service
==================

Orchestrates the complete triage evaluation pipeline:
    1. Load all active rules, trees, and routes
    2. Evaluate ALL rules against the work item → T/F per rule
    3. Walk decision trees in priority order → find first match
    4. Compute route actions → planned field changes
    5. Store evaluation results
    6. Return results (or apply to ADO in Phase 2)

This is the main entry point for triggering evaluations, both
for live processing and test/dry-run mode.

The service coordinates the three engines:
    - RulesEngine: Evaluates atomic rules
    - TreeEngine: Walks decision trees
    - RoutesEngine: Computes field changes
"""

from typing import Dict, List, Optional, Any, Tuple
import logging

from ..engines.rules_engine import RulesEngine
from ..engines.tree_engine import TreeEngine
from ..engines.routes_engine import RoutesEngine, FieldChange
from ..models.rule import Rule
from ..models.action import Action
from ..models.tree import DecisionTree
from ..models.route import Route
from ..models.evaluation import Evaluation, AnalysisState
from ..models.analysis_result import AnalysisResult
from ..config.cosmos_config import get_cosmos_config
from .audit_service import AuditService

logger = logging.getLogger("triage.services.eval")


class EvaluationService:
    """
    Orchestrates the complete triage evaluation pipeline.
    
    Usage:
        service = EvaluationService()
        
        # Full evaluation (returns results, does not write to ADO yet)
        result = service.evaluate(
            work_item_id=12345,
            work_item_data={"System.AreaPath": "UAT\\Triage", ...},
            analysis=analysis_result,
            actor="brad.price@microsoft.com",
            dry_run=False
        )
        
        # Dry run (test mode, no ADO writes, no state changes)
        result = service.evaluate(
            work_item_id=12345,
            work_item_data={...},
            dry_run=True
        )
    """
    
    def __init__(self):
        """Initialize with engines and Cosmos DB connection"""
        self._rules_engine = RulesEngine()
        self._tree_engine = TreeEngine()
        self._routes_engine = RoutesEngine()
        self._cosmos = get_cosmos_config()
        self._audit = AuditService()
    
    def evaluate(
        self,
        work_item_id: int,
        work_item_data: Dict[str, Any],
        analysis: Optional[AnalysisResult] = None,
        actor: str = "system",
        dry_run: bool = False
    ) -> Evaluation:
        """
        Execute the complete evaluation pipeline for a single work item.
        
        Pipeline Steps:
            1. Load all active rules, trees, routes, and actions
            2. Evaluate ALL rules → T/F per rule
            3. Walk trees by priority → find first TRUE match
            4. If match: compute route's field changes
            5. Determine the resulting Analysis.State
            6. Store evaluation record in Cosmos DB
            7. Return the Evaluation result
        
        Args:
            work_item_id:   ADO work item ID
            work_item_data: Work item fields dict
            analysis:       Analysis result (for Analysis.* fields)
            actor:          User who triggered the evaluation
            dry_run:        If True, no ADO writes and no state persistence
            
        Returns:
            Evaluation object with all results
        """
        # Initialize the evaluation record
        evaluation = Evaluation(
            workItemId=work_item_id,
            evaluatedBy=actor,
            isDryRun=dry_run,
        )
        evaluation.generate_id()
        
        mode_label = "DRY RUN" if dry_run else "LIVE"
        logger.info(
            "===== evaluate [%s] item=%s actor=%s eval_id=%s =====",
            mode_label, work_item_id, actor, evaluation.id,
        )
        
        try:
            # ==============================================================
            # Step 1: Load all entities
            # ==============================================================
            rules = self._load_rules()
            trees = self._load_trees()
            actions_dict = self._load_actions_dict()
            routes_dict = self._load_routes_dict()
            
            logger.debug(
                "Step 1 - loaded: %d rules, %d trees, %d actions, %d routes",
                len(rules), len(trees), len(actions_dict), len(routes_dict),
            )
            
            # ==============================================================
            # Step 2: Evaluate ALL rules against the work item
            # ==============================================================
            logger.debug("Step 2 - evaluating rules (include_staged=%s)...", dry_run)
            rule_results, skipped_rules = self._rules_engine.evaluate_all(
                rules=rules,
                work_item=work_item_data,
                analysis=analysis,
                include_staged=dry_run
            )
            
            evaluation.ruleResults = rule_results
            evaluation.skippedRules = skipped_rules
            
            # Track disabled rules that appear in tree expressions,
            # so the evaluation record warns about short-circuited trees.
            disabled_in_trees = set()
            for tree_doc in trees:
                tree_obj = DecisionTree.from_dict(tree_doc) if isinstance(tree_doc, dict) else tree_doc
                for rid in tree_obj.get_referenced_rule_ids():
                    if rid in skipped_rules:
                        disabled_in_trees.add(rid)
            if disabled_in_trees:
                evaluation.errors.append(
                    f"Disabled/skipped rules referenced by trees: "
                    f"{', '.join(sorted(disabled_in_trees))}. "
                    f"These are treated as False and may prevent tree matches."
                )
            
            # ==============================================================
            # Step 3: Walk decision trees in priority order
            # ==============================================================
            logger.debug("Step 3 - walking decision trees...")
            matched_tree_id, route_id, tree_errors = (
                self._tree_engine.evaluate(
                    trees=trees,
                    rule_results=rule_results,
                    skipped_rules=skipped_rules,
                    include_staged=dry_run
                )
            )
            
            evaluation.matchedTree = matched_tree_id
            evaluation.errors.extend(tree_errors)
            
            # ==============================================================
            # Step 4: If a tree matched, compute route field changes
            # ==============================================================
            if route_id and route_id in routes_dict:
                route = routes_dict[route_id]
                logger.debug(
                    "Step 4 - computing changes: tree '%s' → route '%s' (%d actions)",
                    matched_tree_id, route_id, len(route.actions),
                )
                
                changes, route_errors = self._routes_engine.compute_changes(
                    route=route,
                    actions=actions_dict,
                    work_item=work_item_data,
                    analysis=analysis,
                    current_user=actor
                )
                
                evaluation.appliedRoute = route_id
                evaluation.actionsExecuted = [c.action_id for c in changes]
                evaluation.fieldsChanged = {
                    c.field: {"from": c.old_value, "to": c.new_value}
                    for c in changes
                }
                evaluation.errors.extend(route_errors)
                
                # Determine state based on match
                evaluation.analysisState = AnalysisState.AWAITING_APPROVAL
                
            elif matched_tree_id and route_id:
                # Tree matched but route not found
                evaluation.errors.append(
                    f"Matched tree '{matched_tree_id}' points to "
                    f"route '{route_id}' which was not found"
                )
                evaluation.analysisState = AnalysisState.ERROR
                
            else:
                # No tree matched
                logger.debug("Step 4 - no tree matched, state=NO_MATCH")
                evaluation.analysisState = AnalysisState.NO_MATCH
            
            # ==============================================================
            # Step 5: Generate summary HTML
            # ==============================================================
            evaluation.summaryHtml = self._generate_summary_html(
                evaluation, work_item_data, analysis
            )
            
        except Exception as e:
            logger.error(
                "Pipeline error for item %s: %s", work_item_id, e, exc_info=True,
            )
            evaluation.errors.append(f"Pipeline error: {str(e)}")
            evaluation.analysisState = AnalysisState.ERROR
        
        # ==================================================================
        # Step 6: Store evaluation record
        # Dry-run evaluations are also stored so operators can review
        # test results in the Eval History page.
        # ==================================================================
        self._store_evaluation(evaluation)
        
        if not dry_run:
            # Audit log (live evaluations only — dry runs don't warrant audit)
            self._audit.log_evaluation(
                work_item_id=work_item_id,
                actor=actor,
                matched_tree=evaluation.matchedTree,
                applied_route=evaluation.appliedRoute,
                analysis_state=evaluation.analysisState,
                is_dry_run=dry_run
            )
        
        # Log summary
        match_desc = (
            f"→ tree '{evaluation.matchedTree}' → route '{evaluation.appliedRoute}'"
            if evaluation.matchedTree
            else "→ No Match"
        )
        mode = " [DRY RUN]" if dry_run else ""
        logger.info(
            "[%s] Item %s: %d rules evaluated, %d true, %s, state='%s'",
            mode_label, work_item_id,
            evaluation.rules_evaluated_count(),
            evaluation.rules_matched_count(),
            match_desc,
            evaluation.analysisState,
        )
        
        return evaluation
    
    def evaluate_batch(
        self,
        work_items: List[Dict[str, Any]],
        analyses: Optional[Dict[int, AnalysisResult]] = None,
        actor: str = "system",
        dry_run: bool = False
    ) -> List[Evaluation]:
        """
        Evaluate multiple work items.
        
        Args:
            work_items:  List of work item data dicts (must include System.Id)
            analyses:    Dict of workItemId → AnalysisResult
            actor:       User triggering the evaluations
            dry_run:     If True, test mode
            
        Returns:
            List of Evaluation results
        """
        results = []
        analyses = analyses or {}
        
        logger.info(
            "evaluate_batch: %d items, dry_run=%s, actor=%s",
            len(work_items), dry_run, actor,
        )
        
        for item in work_items:
            item_id = item.get("System.Id") or item.get("id")
            if not item_id:
                continue
            
            analysis = analyses.get(item_id)
            result = self.evaluate(
                work_item_id=item_id,
                work_item_data=item,
                analysis=analysis,
                actor=actor,
                dry_run=dry_run
            )
            results.append(result)
        
        return results
    
    def get_evaluation_trace(
        self,
        work_item_id: int,
        work_item_data: Dict[str, Any],
        analysis: Optional[AnalysisResult] = None
    ) -> Dict[str, Any]:
        """
        Generate a detailed evaluation trace for debugging/preview.
        
        Unlike evaluate(), this returns detailed per-tree results
        and does not store anything.
        
        Args:
            work_item_id:   Work item ID
            work_item_data: Work item fields
            analysis:       Analysis result
            
        Returns:
            Dict with detailed trace information
        """
        rules = self._load_rules()
        trees = self._load_trees()
        
        # Evaluate all rules
        rule_results, skipped = self._rules_engine.evaluate_all(
            rules, work_item_data, analysis
        )
        
        # Get detailed tree trace
        tree_trace = self._tree_engine.get_evaluation_trace(
            trees, rule_results, skipped
        )
        
        return {
            "workItemId": work_item_id,
            "ruleResults": rule_results,
            "skippedRules": skipped,
            "treeTrace": tree_trace,
            "rulesEvaluated": len(rule_results),
            "rulesTrue": sum(1 for v in rule_results.values() if v),
        }
    
    # =========================================================================
    # Data Loading
    # =========================================================================
    
    def _load_rules(self) -> List[Rule]:
        """Load all rules from Cosmos DB"""
        container = self._cosmos.get_container("rules")
        items = list(container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        ))
        return [Rule.from_dict(item) for item in items]
    
    def _load_trees(self) -> List[DecisionTree]:
        """Load all trees from Cosmos DB, sorted by priority"""
        container = self._cosmos.get_container("trees")
        items = list(container.query_items(
            query="SELECT * FROM c ORDER BY c.priority",
            enable_cross_partition_query=True
        ))
        return [DecisionTree.from_dict(item) for item in items]
    
    def _load_actions_dict(self) -> Dict[str, Action]:
        """Load all actions as a dict keyed by ID"""
        container = self._cosmos.get_container("actions")
        items = list(container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        ))
        return {item["id"]: Action.from_dict(item) for item in items}
    
    def _load_routes_dict(self) -> Dict[str, Route]:
        """Load all routes as a dict keyed by ID"""
        container = self._cosmos.get_container("routes")
        items = list(container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        ))
        return {item["id"]: Route.from_dict(item) for item in items}
    
    # =========================================================================
    # Storage
    # =========================================================================
    
    def _store_evaluation(self, evaluation: Evaluation) -> None:
        """Store an evaluation record in Cosmos DB"""
        try:
            container = self._cosmos.get_container("evaluations")
            container.create_item(body=evaluation.to_dict())
            logger.debug("Stored evaluation %s for item %s", evaluation.id, evaluation.workItemId)
        except Exception as e:
            logger.error("ERROR storing evaluation %s: %s", evaluation.id, e, exc_info=True)
    
    def get_evaluation_history(
        self,
        work_item_id: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get evaluation history for a work item.
        
        Args:
            work_item_id: ADO work item ID
            limit:        Max entries to return
            
        Returns:
            List of evaluation dicts, newest first
        """
        container = self._cosmos.get_container("evaluations")
        query = (
            "SELECT * FROM c "
            "WHERE c.workItemId = @workItemId "
            "ORDER BY c.date DESC"
        )
        params = [{"name": "@workItemId", "value": work_item_id}]
        
        items = list(container.query_items(
            query=query,
            parameters=params,
            partition_key=work_item_id,
            max_item_count=limit
        ))
        return items
    
    # =========================================================================
    # HTML Summary Generation
    # =========================================================================
    
    def _generate_summary_html(
        self,
        evaluation: Evaluation,
        work_item: Dict[str, Any],
        analysis: Optional[AnalysisResult]
    ) -> str:
        """
        Generate HTML summary for the ADO Challenge Details field.
        
        This HTML is displayed in the ADO work item's Challenge Details
        field, providing a human-readable summary of the evaluation.
        
        Args:
            evaluation: The evaluation results
            work_item:  Work item data
            analysis:   Analysis result
            
        Returns:
            HTML string for Challenge Details
        """
        # Build sections
        sections = []
        
        # Analysis summary (from analysis engine)
        if analysis:
            sections.append(f"""
            <h3>Analysis Summary</h3>
            <table>
                <tr><td><b>Category:</b></td><td>{analysis.category}</td></tr>
                <tr><td><b>Intent:</b></td><td>{analysis.intent}</td></tr>
                <tr><td><b>Confidence:</b></td><td>{analysis.confidence:.0%}</td></tr>
                <tr><td><b>Products:</b></td><td>{', '.join(analysis.detectedProducts)}</td></tr>
                <tr><td><b>Impact:</b></td><td>{analysis.businessImpact}</td></tr>
            </table>
            """)
        
        # Rule evaluation results
        true_rules = [k for k, v in evaluation.ruleResults.items() if v]
        false_rules = [k for k, v in evaluation.ruleResults.items() if not v]
        sections.append(f"""
        <h3>Rules Evaluated</h3>
        <p>{evaluation.rules_evaluated_count()} rules evaluated, 
           {evaluation.rules_matched_count()} matched</p>
        <p><b>True:</b> {', '.join(true_rules) if true_rules else 'None'}</p>
        <p><b>False:</b> {', '.join(false_rules) if false_rules else 'None'}</p>
        """)
        
        # Routing decision
        if evaluation.matchedTree:
            sections.append(f"""
            <h3>Routing Decision</h3>
            <p><b>Matched Tree:</b> {evaluation.matchedTree}</p>
            <p><b>Applied Route:</b> {evaluation.appliedRoute}</p>
            <p><b>Actions:</b> {', '.join(evaluation.actionsExecuted)}</p>
            """)
        else:
            sections.append("""
            <h3>Routing Decision</h3>
            <p><b>No Match</b> - No decision tree matched. Manual triage required.</p>
            """)
        
        # Field changes
        if evaluation.fieldsChanged:
            rows = ""
            for field, change in evaluation.fieldsChanged.items():
                rows += (
                    f"<tr><td>{field}</td>"
                    f"<td>{change.get('from', '-')}</td>"
                    f"<td>{change.get('to', '-')}</td></tr>"
                )
            sections.append(f"""
            <h3>Field Changes</h3>
            <table border="1">
                <tr><th>Field</th><th>From</th><th>To</th></tr>
                {rows}
            </table>
            """)
        
        # State
        sections.append(f"""
        <h3>Result</h3>
        <p><b>Analysis State:</b> {evaluation.analysisState}</p>
        <p><b>Evaluation ID:</b> {evaluation.id}</p>
        <p><b>Date:</b> {evaluation.date}</p>
        """)
        
        # Errors
        if evaluation.errors:
            error_list = "".join(
                f"<li>{err}</li>" for err in evaluation.errors
            )
            sections.append(f"""
            <h3>Warnings/Errors</h3>
            <ul>{error_list}</ul>
            """)
        
        # Combine all sections
        body = "\n".join(sections)
        return f"""
        <div style="font-family: Segoe UI, sans-serif; font-size: 12px;">
            <h2>Triage Evaluation Summary</h2>
            {body}
        </div>
        """
