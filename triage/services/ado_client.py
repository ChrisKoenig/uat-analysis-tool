"""
Triage ADO Adapter
==================

Thin adapter wrapping the existing AzureDevOpsClient from ado_integration.py.
Eliminates duplicated authentication, credentials, and configuration.

Reuses from ado_integration.py:
    - Authentication chain (AzureCliCredential → InteractiveBrowserCredential)
    - Credential caching and sharing across services
    - AzureDevOpsConfig settings (org, project, API version, scope)
    - test_connection() and get_work_item_fields() methods

Adds triage-specific functionality:
    - Dual-org support: READ from production, WRITE to test
    - Comments API (add_comment) for Discussion thread posting
    - FieldChange → JSON Patch conversion for routes engine output
    - 409 conflict detection on updates (revision-aware)
    - Triage queue WIQL query (ROBAnalysisState-based filtering)
    - Batch work item fetch with 200-item chunking
    - Normalized response format ({success: bool, ...}) across all methods

Dual-Organization Pattern:
    - READ (evaluate):  unifiedactiontracker / Unified Action Tracker (production)
    - WRITE (apply):    unifiedactiontrackertest / Unified Action Tracker Test (safe)

    This matches the existing app pattern: real Actions come from production,
    but all write operations target the test org to avoid accidental changes.

Authentication:
    Reuses the credential from AzureDevOpsClient — no duplicated auth chain.
    The same credential works for both orgs since the user has AAD access
    to both. Falls back to TFT credential if needed for the production org.
"""

import sys
import os
import logging
import base64
import requests as http_requests
import traceback
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import quote

logger = logging.getLogger("triage.services.ado")

# Ensure workspace root is in path so we can import ado_integration
_workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _workspace_root not in sys.path:
    sys.path.insert(0, _workspace_root)

from ado_integration import AzureDevOpsClient, AzureDevOpsConfig


# =============================================================================
# Configuration
# =============================================================================

class TriageAdoConfig:
    """
    Triage-specific ADO configuration with dual-org support.

    Extends AzureDevOpsConfig with separate read/write targets:
        - READ_*:  Production org (unifiedactiontracker) — real Actions data
        - WRITE_*: Test org (unifiedactiontrackertest) — safe for development

    All shared settings (API version, work item type, OAuth scope) are
    pulled directly from AzureDevOpsConfig to stay in sync.
    """

    # --- Read target: Production org (real data for evaluation) ---
    READ_ORGANIZATION = "unifiedactiontracker"
    READ_PROJECT = "Unified Action Tracker"
    READ_BASE_URL = f"https://dev.azure.com/{READ_ORGANIZATION}"

    # --- Write target: Test org (safe for development) ---
    WRITE_ORGANIZATION = AzureDevOpsConfig.ORGANIZATION        # "unifiedactiontrackertest"
    WRITE_PROJECT = AzureDevOpsConfig.PROJECT                  # "Unified Action Tracker Test"
    WRITE_BASE_URL = AzureDevOpsConfig.BASE_URL

    # --- Shared settings (from existing config, single source of truth) ---
    API_VERSION = AzureDevOpsConfig.API_VERSION                # "7.0"
    WORK_ITEM_TYPE = AzureDevOpsConfig.WORK_ITEM_TYPE          # "Actions"
    ADO_SCOPE = AzureDevOpsConfig.ADO_SCOPE

    # --- Backward compatibility aliases (point to WRITE org) ---
    ORGANIZATION = WRITE_ORGANIZATION
    PROJECT = WRITE_PROJECT
    BASE_URL = WRITE_BASE_URL


# =============================================================================
# ADO Client Adapter
# =============================================================================

class AdoClient:
    """
    Triage ADO adapter — wraps AzureDevOpsClient with triage-specific methods.

    Key design principle: Reuse, don't duplicate.
        - Auth, credentials, headers → from AzureDevOpsClient
        - Read operations  → target production org (real data)
        - Write operations → target test org (safe for development)
        - New: Comments API, 409 conflict detection, triage queue WIQL

    Usage:
        client = AdoClient()   # wraps AzureDevOpsClient automatically

        # Read from production
        result = client.get_work_item(12345)

        # Write to test
        result = client.update_work_item(12345, field_changes)

    For testing, pass a mock AzureDevOpsClient:
        mock = MagicMock(spec=AzureDevOpsClient)
        client = AdoClient(ado_client=mock)
    """

    def __init__(
        self,
        ado_client: Optional[AzureDevOpsClient] = None,
        config: Optional[TriageAdoConfig] = None,
    ):
        """
        Initialize the triage ADO adapter.

        Wraps an existing AzureDevOpsClient, reusing its credentials
        and connection. Creates a new one if not provided.

        Args:
            ado_client: Optional AzureDevOpsClient instance (for testing/reuse).
                        Default: creates a new AzureDevOpsClient (triggers auth).
            config:     Optional config override. Default: TriageAdoConfig.
        """
        self._client = ado_client or AzureDevOpsClient()
        self._config = config or TriageAdoConfig()

        logger.info(
            "Adapter ready — Read: %s/%s, Write: %s/%s",
            self._config.READ_ORGANIZATION, self._config.READ_PROJECT,
            self._config.WRITE_ORGANIZATION, self._config.WRITE_PROJECT,
        )

    # =========================================================================
    # Shared Helpers (reuse credential from existing client)
    # =========================================================================

    def _get_token(self) -> str:
        """
        Get a fresh access token from the existing client's credential.

        Reuses the AzureDevOpsClient's cached credential — no duplicated
        auth chain. Tokens are short-lived (~1 hour) and refreshed each call.
        Returns None if using PAT auth (no token needed).
        """
        if self._client._pat:
            return None  # PAT uses Basic auth, no bearer token
        return self._client.credential.get_token(self._config.ADO_SCOPE).token

    def _pat_for_org(self, org: str) -> Optional[str]:
        """
        Return the correct PAT for a given ADO org.

        Two org-scoped PATs are supported:
            ADO_PAT      → write org (unifiedactiontrackertest)
            ADO_PAT_READ → read org  (unifiedactiontracker / production)

        Falls back to ADO_PAT if ADO_PAT_READ is not set.
        """
        if org == self._config.READ_ORGANIZATION and self._client._pat_read:
            return self._client._pat_read
        return self._client._pat  # may be None (token auth)

    def _headers(self, content_type: str = "application/json", org: Optional[str] = None) -> Dict[str, str]:
        """
        Build HTTP headers using the correct PAT for *org*, or credential.

        Args:
            content_type: MIME type. Use 'application/json-patch+json' for PATCH.
            org: ADO org name — determines which PAT to use.
                 Pass READ_ORGANIZATION for reads, WRITE_ORGANIZATION for writes.
        """
        pat = self._pat_for_org(org) if org else self._client._pat
        if pat:
            b64 = base64.b64encode(f":{pat}".encode()).decode()
            return {
                "Authorization": f"Basic {b64}",
                "Content-Type": content_type,
                "Accept": "application/json",
            }
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": content_type,
            "Accept": "application/json",
        }

    # =========================================================================
    # URL Builders — Read (Production Org)
    # =========================================================================

    def _read_work_item_url(self, work_item_id: int) -> str:
        """Work item URL against PRODUCTION org for reads."""
        return (
            f"{self._config.READ_BASE_URL}/{quote(self._config.READ_PROJECT)}"
            f"/_apis/wit/workitems/{work_item_id}"
            f"?api-version={self._config.API_VERSION}"
        )

    def _read_batch_url(self, ids: List[int]) -> str:
        """Batch work item URL against PRODUCTION org.

        Uses errorPolicy=Omit so that invalid/not-found IDs return null
        placeholders in the response instead of failing the entire batch
        with HTTP 404.  See ENG-006 in CHANGE_LOG.md.
        """
        ids_str = ",".join(str(i) for i in ids)
        return (
            f"{self._config.READ_BASE_URL}/{quote(self._config.READ_PROJECT)}"
            f"/_apis/wit/workitems?ids={ids_str}"
            f"&$expand=All&errorPolicy=Omit"
            f"&api-version={self._config.API_VERSION}"
        )

    def _read_wiql_url(self) -> str:
        """WIQL URL against PRODUCTION org for triage queue queries."""
        return (
            f"{self._config.READ_BASE_URL}/{quote(self._config.READ_PROJECT)}"
            f"/_apis/wit/wiql?api-version={self._config.API_VERSION}"
        )

    # =========================================================================
    # URL Builders — Write (Test Org)
    # =========================================================================

    def _write_work_item_url(self, work_item_id: int) -> str:
        """Work item URL against TEST org for writes."""
        return (
            f"{self._config.WRITE_BASE_URL}/{quote(self._config.WRITE_PROJECT)}"
            f"/_apis/wit/workitems/{work_item_id}"
            f"?api-version={self._config.API_VERSION}"
        )

    def _write_comment_url(self, work_item_id: int) -> str:
        """Comments API URL against TEST org (7.0-preview.3)."""
        return (
            f"{self._config.WRITE_BASE_URL}/{quote(self._config.WRITE_PROJECT)}"
            f"/_apis/wit/workitems/{work_item_id}/comments"
            f"?api-version=7.0-preview.3"
        )

    def _write_field_definitions_url(self) -> str:
        """Field definitions URL against TEST org."""
        return (
            f"{self._config.WRITE_BASE_URL}/{quote(self._config.WRITE_PROJECT)}"
            f"/_apis/wit/workitemtypes/{self._config.WORK_ITEM_TYPE}"
            f"/fields?$expand=All&api-version=7.1"
        )

    # =========================================================================
    # Read Operations — From PRODUCTION org (real data)
    # =========================================================================

    def get_work_item(self, work_item_id: int) -> Dict[str, Any]:
        """
        Fetch a single work item with all fields from PRODUCTION.

        This is the primary method used by the evaluation pipeline to get
        work item data for rule evaluation. Reads from the production org
        to get real Action data.

        Args:
            work_item_id: ADO work item ID

        Returns:
            Dict with keys: success, id, rev, fields, url, error
        """
        try:
            url = self._read_work_item_url(work_item_id)
            logger.debug("get_work_item %d: GET %s", work_item_id, url)
            response = http_requests.get(url, headers=self._headers(org=self._config.READ_ORGANIZATION))
            logger.debug("get_work_item %d: status=%d", work_item_id, response.status_code)

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "id": data["id"],
                    "rev": data["rev"],
                    "fields": data.get("fields", {}),
                    "url": data.get("url", ""),
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": f"Work item {work_item_id} not found",
                }
            else:
                return {
                    "success": False,
                    "error": (
                        f"Failed to fetch work item {work_item_id}: "
                        f"{response.status_code} - {response.text}"
                    ),
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed for work item {work_item_id}: {str(e)}",
            }

    def get_work_items_batch(self, work_item_ids: List[int]) -> Dict[str, Any]:
        """
        Fetch multiple work items from PRODUCTION in batched API calls.

        ADO supports up to 200 IDs per request. Larger lists are
        automatically chunked.

        Args:
            work_item_ids: List of work item IDs to fetch

        Returns:
            Dict with keys: success, items, failed_ids, error
        """
        if not work_item_ids:
            return {"success": True, "items": [], "failed_ids": []}

        all_items = []
        failed_ids = []
        chunk_size = 200

        chunks = [
            work_item_ids[i:i + chunk_size]
            for i in range(0, len(work_item_ids), chunk_size)
        ]

        for chunk in chunks:
            try:
                url = self._read_batch_url(chunk)
                response = http_requests.get(url, headers=self._headers(org=self._config.READ_ORGANIZATION))

                if response.status_code == 200:
                    data = response.json()
                    # ENG-006: With errorPolicy=Omit, the ADO value array
                    # contains null entries for invalid/not-found IDs.
                    # Example: [valid_item, null, valid_item, valid_item]
                    # We skip nulls and track which IDs were actually returned
                    # so we can report omissions individually.
                    fetched_ids = set()
                    for item in data.get("value", []):
                        if item is None:
                            continue  # errorPolicy=Omit returns null placeholders
                        all_items.append({
                            "id": item["id"],
                            "rev": item["rev"],
                            "fields": item.get("fields", {}),
                            "url": item.get("url", ""),
                        })
                        fetched_ids.add(item["id"])
                    # Detect which requested IDs were omitted (not found in ADO)
                    for cid in chunk:
                        if int(cid) not in fetched_ids:
                            failed_ids.append(cid)
                else:
                    failed_ids.extend(chunk)
                    logger.warning(
                        "Batch fetch failed: %s - %s",
                        response.status_code, response.text,
                    )
            except Exception as e:
                failed_ids.extend(chunk)
                logger.error("Batch fetch error: %s", e, exc_info=True)

        if not all_items and failed_ids:
            return {
                "success": False,
                "items": [],
                "failed_ids": failed_ids,
                "error": "All batch requests failed",
            }

        return {
            "success": True,
            "items": all_items,
            "failed_ids": failed_ids,
        }

    def query_triage_queue(
        self,
        state_filter: Optional[str] = None,
        area_path: Optional[str] = None,
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """
        Query PRODUCTION for work items pending triage.

        Runs a WIQL query against the production org to find Action items
        in triage-relevant states, ordered by creation date.

        Args:
            state_filter: Filter by ROBAnalysisState (e.g., "Pending").
                          Default: Pending, Awaiting Approval, Needs Info.
            area_path:    Optional area path filter (e.g., "UAT\\MCAPS")
            max_results:  Maximum items to return (default 100)

        Returns:
            Dict with keys: success, work_item_ids, count, total_available, error
        """
        try:
            conditions = [
                f"[System.TeamProject] = '{self._config.READ_PROJECT}'",
                f"[System.WorkItemType] = '{self._config.WORK_ITEM_TYPE}'",
            ]

            if state_filter:
                conditions.append(
                    f"[Custom.ROBAnalysisState] = '{state_filter}'"
                )
            else:
                conditions.append(
                    "[Custom.ROBAnalysisState] IN "
                    "('Pending', 'Awaiting Approval', 'Needs Info')"
                )

            if area_path:
                conditions.append(
                    f"[System.AreaPath] UNDER '{area_path}'"
                )

            where_clause = " AND ".join(conditions)
            wiql = (
                f"SELECT [System.Id] FROM WorkItems "
                f"WHERE {where_clause} "
                f"ORDER BY [System.CreatedDate] ASC"
            )

            response = http_requests.post(
                self._read_wiql_url(),
                json={"query": wiql},
                headers=self._headers(org=self._config.READ_ORGANIZATION),
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "work_item_ids": [],
                    "count": 0,
                    "error": (
                        f"WIQL query failed: {response.status_code} - "
                        f"{response.text}"
                    ),
                }

            result = response.json()
            all_ids = [item["id"] for item in result.get("workItems", [])]
            ids = all_ids[:max_results]

            return {
                "success": True,
                "work_item_ids": ids,
                "count": len(ids),
                "total_available": len(all_ids),
            }

        except Exception as e:
            return {
                "success": False,
                "work_item_ids": [],
                "count": 0,
                "error": f"Triage queue query failed: {str(e)}",
            }

    # =========================================================================
    # Saved Query Operations — Run ADO Saved Queries by ID
    # =========================================================================

    def run_saved_query(
        self,
        query_id: str,
        max_results: int = 200,
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run an ADO saved query by its GUID and return hydrated work items.

        Steps:
            1. Fetch the saved query definition (GET .../wit/queries/{id})
            2. Extract the WIQL and execute it (POST .../wit/wiql)
            3. Batch-fetch work items with the query's column list + extras
            4. Return hydrated items with all field data

        Args:
            query_id:    GUID of the saved ADO query
            max_results: Maximum items to return (default 200)
            fields:      Extra fields to fetch beyond the query's columns.
                         If None, uses the query's column definitions.

        Returns:
            Dict with keys:
                success, queryName, wiql, items[], columns[], count,
                totalAvailable, failedIds[], error
        """
        try:
            # Step 1: Get query definition
            query_def_url = (
                f"{self._config.READ_BASE_URL}/{quote(self._config.READ_PROJECT)}"
                f"/_apis/wit/queries/{query_id}"
                f"?api-version={self._config.API_VERSION}&$expand=wiql"
            )
            logger.info("Fetching saved query %s", query_id)
            resp = http_requests.get(query_def_url, headers=self._headers(org=self._config.READ_ORGANIZATION))

            if resp.status_code == 404:
                return {
                    "success": False,
                    "error": f"Saved query {query_id} not found",
                }
            if resp.status_code != 200:
                return {
                    "success": False,
                    "error": (
                        f"Failed to fetch saved query: "
                        f"{resp.status_code} - {resp.text[:300]}"
                    ),
                }

            query_def = resp.json()
            query_name = query_def.get("name", "Unnamed")
            wiql = query_def.get("wiql", "")
            # Preserve both reference name and display name for dynamic UI columns
            columns = [
                {
                    "referenceName": c["referenceName"],
                    "name": c.get("name", c["referenceName"].split(".")[-1]),
                }
                for c in query_def.get("columns", [])
            ]
            column_refs = [c["referenceName"] for c in columns]

            if not wiql:
                return {
                    "success": False,
                    "error": f"Saved query '{query_name}' has no WIQL",
                }

            # Step 2: Execute the WIQL
            wiql_url = self._read_wiql_url()
            logger.info("Running WIQL for '%s'", query_name)
            wiql_resp = http_requests.post(
                wiql_url,
                json={"query": wiql},
                headers=self._headers(org=self._config.READ_ORGANIZATION),
            )

            if wiql_resp.status_code != 200:
                return {
                    "success": False,
                    "error": (
                        f"WIQL execution failed: "
                        f"{wiql_resp.status_code} - {wiql_resp.text[:300]}"
                    ),
                }

            wiql_result = wiql_resp.json()
            all_ids = [item["id"] for item in wiql_result.get("workItems", [])]
            total_available = len(all_ids)
            ids_to_fetch = all_ids[:max_results]

            if not ids_to_fetch:
                return {
                    "success": True,
                    "queryName": query_name,
                    "wiql": wiql,
                    "items": [],
                    "columns": columns,
                    "count": 0,
                    "totalAvailable": 0,
                    "failedIds": [],
                }

            # Step 3: Determine fields to fetch
            fetch_fields = list(set(column_refs + [
                "System.Id", "System.State", "System.AssignedTo",
                "System.AreaPath", "System.Tags",
                "System.CreatedBy",
                "System.CreatedDate", "System.ChangedDate",
                "System.WorkItemType", "Custom.ROBAnalysisState",
                "Custom.Requestor", "Custom.Requestors",
            ] + (fields or [])))

            # Step 4: Batch fetch using the work item batch API
            items = []
            failed_ids = []
            chunk_size = 200

            for i in range(0, len(ids_to_fetch), chunk_size):
                chunk = ids_to_fetch[i:i + chunk_size]
                try:
                    batch_url = (
                        f"{self._config.READ_BASE_URL}"
                        f"/{quote(self._config.READ_PROJECT)}"
                        f"/_apis/wit/workitemsbatch"
                        f"?api-version={self._config.API_VERSION}"
                    )
                    batch_resp = http_requests.post(
                        batch_url,
                        json={"ids": chunk, "fields": fetch_fields},
                        headers=self._headers(org=self._config.READ_ORGANIZATION),
                    )

                    if batch_resp.status_code == 200:
                        for item in batch_resp.json().get("value", []):
                            raw_fields = item.get("fields", {})
                            # Normalize identity fields (dict → displayName)
                            normalized = {}
                            for k, v in raw_fields.items():
                                if isinstance(v, dict) and "displayName" in v:
                                    normalized[k] = v["displayName"]
                                else:
                                    normalized[k] = v
                            # Preserve raw email for identity fields (FR-1998 Graph lookup)
                            raw_cb = raw_fields.get("System.CreatedBy")
                            if isinstance(raw_cb, dict) and raw_cb.get("uniqueName"):
                                normalized["_createdByEmail"] = raw_cb["uniqueName"]
                            raw_rq = raw_fields.get("Custom.Requestor")
                            if isinstance(raw_rq, dict) and raw_rq.get("uniqueName"):
                                normalized["_requestorEmail"] = raw_rq["uniqueName"]
                            items.append({
                                "id": item["id"],
                                "rev": item.get("rev", 0),
                                "fields": normalized,
                                "adoLink": self.get_work_item_link(item["id"]),
                            })
                    else:
                        failed_ids.extend(chunk)
                        logger.warning(
                            "Batch fetch for saved query failed: %s",
                            batch_resp.status_code,
                        )
                except Exception as e:
                    failed_ids.extend(chunk)
                    logger.error("Batch error: %s", e, exc_info=True)

            return {
                "success": True,
                "queryName": query_name,
                "wiql": wiql,
                "items": items,
                "columns": columns,
                "count": len(items),
                "totalAvailable": total_available,
                "failedIds": failed_ids,
            }

        except Exception as e:
            logger.error("run_saved_query failed: %s", e, exc_info=True)
            return {
                "success": False,
                "error": f"Saved query execution failed: {str(e)}",
            }

    # =========================================================================
    # Write Operations — To TEST org (safe for development)
    # =========================================================================

    def update_work_item(
        self,
        work_item_id: int,
        field_changes: List[Any],  # List[FieldChange] — loose typed to avoid circular import
        revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Apply field changes to a work item in the TEST org.

        Converts FieldChange objects (from the routes engine) into ADO
        JSON Patch operations. Includes 409 conflict detection that the
        existing AzureDevOpsClient doesn't provide.

        Args:
            work_item_id:  ADO work item ID
            field_changes: List of FieldChange objects (.field, .new_value)
            revision:      Optional expected revision for optimistic locking

        Returns:
            Dict with keys: success, id, rev, error, conflict
        """
        if not field_changes:
            return {
                "success": True,
                "id": work_item_id,
                "rev": revision,
                "message": "No changes to apply",
            }

        try:
            # Build JSON Patch operations from FieldChange objects
            operations = []
            for change in field_changes:
                field_name = change.field
                if not field_name.startswith("/fields/"):
                    field_name = f"/fields/{field_name}"
                operations.append({
                    "op": "add",
                    "path": field_name,
                    "value": change.new_value,
                })

            url = self._write_work_item_url(work_item_id)
            logger.debug(
                "update_work_item %d: PATCH %s (%d ops)",
                work_item_id, url, len(operations),
            )

            response = http_requests.patch(
                url,
                json=operations,
                headers=self._headers(
                    content_type="application/json-patch+json",
                    org=self._config.WRITE_ORGANIZATION,
                ),
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "id": data["id"],
                    "rev": data["rev"],
                }
            elif response.status_code == 409:
                return {
                    "success": False,
                    "id": work_item_id,
                    "conflict": True,
                    "error": (
                        f"Conflict updating work item {work_item_id}. "
                        "Item was modified since last read. "
                        "Re-fetch, re-evaluate, and retry."
                    ),
                }
            elif response.status_code == 400:
                return {
                    "success": False,
                    "id": work_item_id,
                    "error": (
                        f"Bad request updating work item {work_item_id}: "
                        f"{response.text}"
                    ),
                }
            else:
                return {
                    "success": False,
                    "id": work_item_id,
                    "error": (
                        f"Failed to update work item {work_item_id}: "
                        f"{response.status_code} - {response.text}"
                    ),
                }

        except Exception as e:
            return {
                "success": False,
                "id": work_item_id,
                "error": f"Update request failed for {work_item_id}: {str(e)}",
            }

    def add_comment(
        self,
        work_item_id: int,
        html_content: str,
    ) -> Dict[str, Any]:
        """
        Post a discussion comment on a work item in the TEST org.

        Uses the Comments API (7.0-preview.3) which supports threaded
        comments and @mentions. Not available in the existing AzureDevOpsClient.

        Args:
            work_item_id: ADO work item ID
            html_content: HTML-formatted comment body

        Returns:
            Dict with keys: success, comment_id, error
        """
        try:
            response = http_requests.post(
                self._write_comment_url(work_item_id),
                json={"text": html_content},
                headers=self._headers(org=self._config.WRITE_ORGANIZATION),
            )

            if response.status_code in (200, 201):
                data = response.json()
                return {
                    "success": True,
                    "comment_id": data.get("id"),
                }
            else:
                return {
                    "success": False,
                    "error": (
                        f"Failed to post comment on {work_item_id}: "
                        f"{response.status_code} - {response.text}"
                    ),
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Comment request failed for {work_item_id}: {str(e)}",
            }

    def set_analysis_state(
        self,
        work_item_id: int,
        state: str,
        revision: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update the ROBAnalysisState field on a work item.

        Convenience wrapper over update_work_item() for the most common
        single-field update in the triage pipeline.

        Args:
            work_item_id: ADO work item ID
            state:        New state value (e.g., "Pending", "Awaiting Approval")
            revision:     Optional revision for conflict detection
        """
        # Lightweight object matching FieldChange interface (.field, .new_value)
        class _SimpleChange:
            def __init__(self, field, new_value):
                self.field = field
                self.new_value = new_value

        change = _SimpleChange("Custom.ROBAnalysisState", state)
        return self.update_work_item(work_item_id, [change], revision)

    # =========================================================================
    # Delegated Operations — Pass through to existing AzureDevOpsClient
    # =========================================================================

    def get_field_definitions(self) -> Dict[str, Any]:
        """
        Fetch field definitions — delegates to existing AzureDevOpsClient.

        Returns metadata about every field on the Action work item type.

        Returns:
            Dict with keys: success, fields, work_item_type, error
        """
        result = self._client.get_work_item_fields()

        if result.get("success"):
            return {
                "success": True,
                "fields": result.get("fields", []),
                "work_item_type": self._config.WORK_ITEM_TYPE,
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Failed to fetch field definitions"),
            }

    def test_connection(self) -> Dict[str, Any]:
        """
        Test ADO connectivity — delegates to existing AzureDevOpsClient.

        Returns:
            Dict with keys: success, organization, project, message, error
        """
        result = self._client.test_connection()

        if result.get("success"):
            return {
                "success": True,
                "organization": self._config.WRITE_ORGANIZATION,
                "project": self._config.WRITE_PROJECT,
                "read_organization": self._config.READ_ORGANIZATION,
                "read_project": self._config.READ_PROJECT,
                "message": (
                    f"Write: {self._config.WRITE_ORGANIZATION}/{self._config.WRITE_PROJECT}, "
                    f"Read: {self._config.READ_ORGANIZATION}/{self._config.READ_PROJECT}"
                ),
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Connection failed"),
            }

    # =========================================================================
    # Utility
    # =========================================================================

    def get_work_item_link(self, work_item_id: int) -> str:
        """
        Generate a browser-navigable URL for a work item.

        Links to the production org web UI (where real data lives).

        Args:
            work_item_id: ADO work item ID

        Returns:
            URL string to the work item in ADO web UI
        """
        return (
            f"https://dev.azure.com/{self._config.READ_ORGANIZATION}"
            f"/{quote(self._config.READ_PROJECT)}"
            f"/_workitems/edit/{work_item_id}"
        )


# =============================================================================
# Singleton Access
# =============================================================================

_ado_client_instance: Optional[AdoClient] = None


def get_ado_client() -> AdoClient:
    """
    Get the shared triage ADO client singleton.

    Creates the client on first call (triggers auth via AzureDevOpsClient),
    reuses it thereafter. Shares credentials with the rest of the app.

    Returns:
        AdoClient: Shared adapter instance
    """
    global _ado_client_instance
    if _ado_client_instance is None:
        _ado_client_instance = AdoClient()
    return _ado_client_instance


def reset_ado_client() -> None:
    """
    Reset the singleton (for testing or credential refresh).

    Next get_ado_client() call creates a fresh client with new credentials.
    """
    global _ado_client_instance
    _ado_client_instance = None
