#!/usr/bin/env python3
"""
Azure DevOps Integration Module

This module provides comprehensive integration with Azure DevOps REST APIs for work item
management, specifically designed for the Enhanced Issue Tracker System.

⚠️ PRODUCTION DEPLOYMENT NOTE:
   Currently using Azure CLI authentication for development.
   Before production deployment, switch to Service Principal authentication:
   - Create Azure AD App Registration
   - Grant appropriate Azure DevOps permissions
   - Use client_id/client_secret instead of CLI credentials
   - Update AzureDevOpsConfig to use Service Principal

Key Features:
- Work item creation with custom fields and formatting
- Authentication using Azure CLI credentials (dev) / Service Principal (prod)
- Error handling and validation for API operations
- Support for custom work item types (Action items)
- Project and organization management

Classes:
    AzureDevOpsConfig: Configuration container for API settings and credentials
    AzureDevOpsClient: Main client for Azure DevOps REST API operations

Author: Enhanced Issue Tracker System
Version: 2.1
Last Updated: December 2025
"""

import requests
import json
import os
import base64
from typing import Dict, List, Optional, Any
from urllib.parse import quote
from azure.identity import AzureCliCredential, InteractiveBrowserCredential, ManagedIdentityCredential


def _cfg_ado_org() -> str:
    val = os.environ.get("ADO_ORGANIZATION")
    if val:
        return val
    try:
        from config import get_app_config
        return get_app_config().ado_organization
    except Exception:
        return "unifiedactiontrackertest"


def _cfg_ado_project() -> str:
    val = os.environ.get("ADO_PROJECT")
    if val:
        return val
    try:
        from config import get_app_config
        return get_app_config().ado_project
    except Exception:
        return "Unified Action Tracker Test"


class AzureDevOpsConfig:
    """
    Configuration container for Azure DevOps integration settings.
    
    Centralizes all configuration parameters for Azure DevOps API access,
    including authentication, project details, and API versioning.
    
    Attributes:
        ORGANIZATION (str): Azure DevOps organization name
        PROJECT (str): Target project name for work item creation
        BASE_URL (str): Complete base URL for API endpoints
        API_VERSION (str): Azure DevOps REST API version
        WORK_ITEM_TYPE (str): Default work item type for new items
        PAT (str): Personal Access Token for authentication
    """
    ORGANIZATION = _cfg_ado_org()
    PROJECT = _cfg_ado_project()
    BASE_URL = f"https://dev.azure.com/{ORGANIZATION}"
    API_VERSION = "7.0"
    # Test org uses "Action" (singular), production uses "Actions" (plural)
    WORK_ITEM_TYPE = "Action" if ORGANIZATION == "unifiedactiontrackertest" else "Actions"
    
    # Azure DevOps scope for authentication
    ADO_SCOPE = "499b84ac-1321-427f-aa17-267ca6975798/.default"  # Azure DevOps scope
    
    # Cached credentials to reuse across operations
    # Two separate credentials are needed because:
    # 1. Main org (unifiedactiontrackertest) - for work item creation
    # 2. TFT org (unifiedactiontracker/Technical Feedback) - for feature search
    # Both use browser-based authentication but are cached separately to avoid
    # repeated authentication prompts within the same session
    _cached_credential = None  # Main organization credential
    _cached_tft_credential = None  # Technical Feedback organization credential
    
    @staticmethod
    def get_credential():
        """
        Get Azure credential for ADO authentication.

        Auth chain (in order):
        1. Return in-memory cached credential (same process)
        2. ManagedIdentityCredential (headless container deployment)
        3. InteractiveBrowserCredential with persistent disk cache
           - If a valid token exists in the cache: returns silently (no popup)
           - If token expired but refresh token exists: refreshes silently
           - Otherwise: opens browser for interactive login

        NOTE: This credential is intentionally SEPARATE from shared_auth.py.
        shared_auth forces tenant 16b3c013-... (for Azure OpenAI), but ADO
        orgs need the user's home tenant.  We do NOT use AzureCliCredential
        because az-login is typically pointed at the OpenAI tenant, which
        returns a token whose identity is not materialized in ADO.

        Returns:
            Azure credential object
        """
        from azure.identity import (
            InteractiveBrowserCredential,
            ManagedIdentityCredential,
            TokenCachePersistenceOptions,
        )

        # ── Persistent cache name (shared with enhanced_matching) ──
        ADO_CACHE_NAME = "gcs-ado-auth"

        # Return our own cached credential if available
        if AzureDevOpsConfig._cached_credential is not None:
            return AzureDevOpsConfig._cached_credential

        # 1. Managed Identity — for container/cloud deployment (headless)
        # Falls back to AZURE_CLIENT_ID if ADO_MANAGED_IDENTITY_CLIENT_ID is not set.
        # This is needed for App Service pre-prod where AZURE_CLIENT_ID is the MI
        # configured on the App Service but ADO_MANAGED_IDENTITY_CLIENT_ID may not be set.
        ado_mi_client_id = os.environ.get("ADO_MANAGED_IDENTITY_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID")
        if ado_mi_client_id:
            print(f"[AUTH] Trying Managed Identity credential for ADO (client_id={ado_mi_client_id[:8]}...)...")
            try:
                credential = ManagedIdentityCredential(client_id=ado_mi_client_id)
                token = credential.get_token(AzureDevOpsConfig.ADO_SCOPE)
                print("[AUTH] Managed Identity authentication successful for ADO")
                AzureDevOpsConfig._cached_credential = credential
                return credential
            except Exception as mi_error:
                print(f"[AUTH] Managed Identity failed: {mi_error}")

        # 2. Try shared_auth credential — but VERIFY with a real API call.
        #    AzureCliCredential may get a valid AAD token but the identity
        #    may not be materialized in the ADO org (returns 403).
        try:
            from shared_auth import get_credential as get_shared_credential
            shared_cred = get_shared_credential()
            if shared_cred is not None:
                print("[AUTH] Trying shared auth credential for ADO (verifying with API call)...")
                if AzureDevOpsConfig._verify_org_access(shared_cred, AzureDevOpsConfig.ORGANIZATION):
                    token = shared_cred.get_token(AzureDevOpsConfig.ADO_SCOPE)
                    print("[AUTH] Shared auth credential verified for ADO — reusing")
                    AzureDevOpsConfig._cached_credential = shared_cred
                    try:
                        from enhanced_matching import EnhancedMatchingConfig
                        EnhancedMatchingConfig._uat_credential = shared_cred
                        EnhancedMatchingConfig._uat_token = token.token
                    except Exception:
                        pass
                    return shared_cred
                else:
                    print("[AUTH] Shared auth credential not materialized in ADO org")
        except Exception as e:
            print(f"[AUTH] Shared auth credential not available for ADO: {e}")

        # 3. Interactive Browser with persistent disk cache
        #    No tenant_id → user's home tenant (required for unifiedactiontrackertest).
        #    Persistent cache survives server restarts / uvicorn --reload.
        cache_opts = TokenCachePersistenceOptions(name=ADO_CACHE_NAME)
        print("[AUTH] Using Interactive Browser credential for ADO (persistent cache)...")
        try:
            credential = InteractiveBrowserCredential(
                cache_persistence_options=cache_opts,
            )
            token = credential.get_token(AzureDevOpsConfig.ADO_SCOPE)
            print("[AUTH] ADO authentication successful (token cached to disk)")
            AzureDevOpsConfig._cached_credential = credential

            # Share with search services so they don't prompt separately
            try:
                from enhanced_matching import EnhancedMatchingConfig
                EnhancedMatchingConfig._uat_credential = credential
                EnhancedMatchingConfig._uat_token = token.token
                print("[AUTH] Credential shared with UAT search services")
            except Exception:
                pass

            return credential
        except Exception as e:
            print(f"[AUTH] Interactive Browser authentication failed: {e}")
            raise Exception(
                "ADO authentication failed. Please complete the browser login "
                "when prompted, or visit https://dev.azure.com/unifiedactiontrackertest "
                "in your browser to materialize your identity."
            )
    
    @staticmethod
    def _verify_org_access(credential, org: str) -> bool:
        """
        Verify a credential can actually call an ADO org's API.

        get_token() alone is NOT sufficient — AAD happily issues a token for
        any credential, but the ADO org may reject it with 403 if the
        identity hasn't been "materialized" (never logged in interactively).
        """
        import requests as _req
        token = credential.get_token(AzureDevOpsConfig.ADO_SCOPE).token
        url = f"https://dev.azure.com/{org}/_apis/projects?api-version=7.0&$top=1"
        r = _req.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if r.status_code == 200:
            return True
        print(f"[AUTH] {org} API returned {r.status_code} — credential not materialized")
        return False

    @staticmethod
    def _verify_tft_access(credential) -> bool:
        """Verify a credential can access the TFT ADO org."""
        try:
            from config import get_app_config as _gcfg
            tft_org = _gcfg().ado_tft_organization
        except Exception:
            tft_org = "unifiedactiontracker"
        return AzureDevOpsConfig._verify_org_access(credential, tft_org)

    @staticmethod
    def get_tft_credential():
        """
        Get Azure credential for Technical Feedback organization access.
        The TFT org (unifiedactiontracker) lives in the Microsoft tenant.

        Auth chain (in order):
        1. Return cached TFT credential (already verified)
        2. Reuse main-org credential — but VERIFY with a real TFT API call
           (get_token alone is not enough — the org may reject unmaterialized identities)
        3. ManagedIdentityCredential — fail-fast if MI is set but fails
        4. Shared auth credential — verified with real API call
        5. SharedTokenCacheCredential with Microsoft tenant (local, picks up prior login)
        6. InteractiveBrowserCredential with Microsoft tenant (local last resort,
           materializes the identity in the TFT org)

        Returns:
            Azure credential object configured for TFT org access
        """
        MICROSOFT_TENANT = "72f988bf-86f1-41af-91ab-2d7cd011db47"
        TFT_CACHE_NAME = "gcs-ado-tft-auth"

        # 1. Return cached credential if available (already verified on first use)
        if AzureDevOpsConfig._cached_tft_credential is not None:
            print("[AUTH] Reusing cached TFT credential...")
            return AzureDevOpsConfig._cached_tft_credential

        # 2. Reuse main-org credential — but verify it actually works against TFT org.
        #    AzureCliCredential may get a token from the wrong tenant whose identity
        #    isn't materialized in the TFT ADO org, so get_token() alone is NOT enough.
        if AzureDevOpsConfig._cached_credential is not None:
            try:
                print("[AUTH] Trying main org credential for TFT org (verifying with API call)...")
                if AzureDevOpsConfig._verify_tft_access(AzureDevOpsConfig._cached_credential):
                    AzureDevOpsConfig._cached_tft_credential = AzureDevOpsConfig._cached_credential
                    print("[AUTH] Main org credential reused for TFT — verified with API call")
                    return AzureDevOpsConfig._cached_tft_credential
                else:
                    print("[AUTH] Main org credential token works but identity not materialized in TFT org")
            except Exception as e:
                print(f"[AUTH] Main org credential doesn't work for TFT: {e}")

        # 3. Managed Identity — for container / cloud deployment
        ado_mi_client_id = os.environ.get("ADO_MANAGED_IDENTITY_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID")
        if ado_mi_client_id:
            print(f"[AUTH] Trying Managed Identity credential for TFT (client_id={ado_mi_client_id[:8]}...)...")
            try:
                from azure.identity import ManagedIdentityCredential
                credential = ManagedIdentityCredential(client_id=ado_mi_client_id)
                credential.get_token(AzureDevOpsConfig.ADO_SCOPE)
                AzureDevOpsConfig._cached_tft_credential = credential
                print("[AUTH] Managed Identity authentication successful for TFT")
                return credential
            except Exception as mi_error:
                # In production with MI, do NOT fall through to interactive methods
                # that would hang forever on a headless App Service.
                print(f"[ERROR] Managed Identity TFT credential failed: {mi_error}")
                raise Exception(
                    f"TFT authentication failed via Managed Identity: {mi_error}. "
                    "Ensure the Managed Identity (TechRoB-Automation-DEV) has been "
                    "added to the TFT ADO org (unifiedactiontracker)."
                )

        # 4. Try shared_auth credential — verified with real API call
        try:
            from shared_auth import get_credential as get_shared_credential
            shared_cred = get_shared_credential()
            if shared_cred is not None:
                print("[AUTH] Trying shared auth credential for TFT (verifying with API call)...")
                if AzureDevOpsConfig._verify_tft_access(shared_cred):
                    AzureDevOpsConfig._cached_tft_credential = shared_cred
                    print("[AUTH] Shared auth credential verified for TFT — reusing")
                    return shared_cred
                else:
                    print("[AUTH] Shared auth credential not materialized in TFT org")
        except Exception as e:
            print(f"[AUTH] Shared auth credential not available for TFT: {e}")

        # 5. SharedTokenCache — picks up a previous browser login (local only)
        try:
            from azure.identity import SharedTokenCacheCredential, TokenCachePersistenceOptions
            cache_opts = TokenCachePersistenceOptions(name=TFT_CACHE_NAME)
            print("[AUTH] Checking persistent token cache for TFT...")
            shared_cred = SharedTokenCacheCredential(
                tenant_id=MICROSOFT_TENANT,
                cache_persistence_options=cache_opts,
            )
            if AzureDevOpsConfig._verify_tft_access(shared_cred):
                AzureDevOpsConfig._cached_tft_credential = shared_cred
                print("[AUTH] TFT persistent cache hit — verified with API call")
                return shared_cred
            else:
                print("[AUTH] Cached TFT token not materialized in org")
        except Exception as cache_err:
            print(f"[AUTH] No usable cached TFT token ({cache_err})")

        # 6. Interactive Browser with Microsoft tenant (local last resort)
        #    This materializes the identity in the TFT ADO org.
        from azure.identity import InteractiveBrowserCredential, TokenCachePersistenceOptions
        cache_opts = TokenCachePersistenceOptions(name=TFT_CACHE_NAME)
        print("[AUTH] Creating TFT credential via browser (Microsoft tenant, persistent cache)...")
        print("[AUTH] A browser window will open — this materializes your identity in the TFT org.")
        credential = InteractiveBrowserCredential(
            tenant_id=MICROSOFT_TENANT,
            cache_persistence_options=cache_opts,
        )
        credential.get_token(AzureDevOpsConfig.ADO_SCOPE)
        AzureDevOpsConfig._cached_tft_credential = credential
        print("[AUTH] TFT credential cached for reuse (Microsoft tenant)")
        return credential


class AzureDevOpsClient:
    """
    Client for Azure DevOps REST API operations.
    
    Uses Azure CLI authentication for development. For production deployment,
    update to use Service Principal authentication.
    
    Provides a comprehensive interface for interacting with Azure DevOps work items,
    including creation, testing connectivity, and error handling. Designed specifically
    for the Enhanced Issue Tracker System's workflow requirements.
    
    Attributes:
        config (AzureDevOpsConfig): Configuration object with API settings
        headers (Dict[str, str]): HTTP headers for API authentication
    """
    
    def __init__(self):
        """
        Initialize the Azure DevOps client with configuration and authentication.
        
        Sets up the client with proper authentication headers and configuration.
        Auth priority: ADO_PAT env var > ManagedIdentity > CLI > Browser
        """
        self.config = AzureDevOpsConfig()
        self._pat = os.environ.get("ADO_PAT")
        self._pat_read = os.environ.get("ADO_PAT_READ")
        if self._pat:
            print("[AUTH] Using PAT token for ADO authentication (write org)")
            if self._pat_read:
                print("[AUTH] Using separate PAT for read org (production)")
            self.credential = None  # Not needed with PAT
        else:
            self.credential = self.config.get_credential()
        self.headers = self._get_headers()
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for Azure DevOps API calls.
        
        Uses PAT (Basic auth) if ADO_PAT is set, otherwise uses Azure credential
        (Bearer token) for authentication.
        
        Returns:
            Dict[str, str]: HTTP headers including Authorization, Content-Type, and Accept
        """
        try:
            if self._pat:
                # PAT uses Basic auth with base64(:PAT)
                b64 = base64.b64encode(f":{self._pat}".encode()).decode()
                return {
                    'Content-Type': 'application/json-patch+json',
                    'Authorization': f'Basic {b64}',
                    'Accept': 'application/json'
                }
            # Bearer token from credential
            token = self.credential.get_token(self.config.ADO_SCOPE)
            
            return {
                'Content-Type': 'application/json-patch+json',
                'Authorization': f'Bearer {token.token}',
                'Accept': 'application/json'
            }
        except Exception as e:
            print(f"[ERROR] Failed to get Azure DevOps token: {e}")
            print("[INFO] Run 'az login' to authenticate with Azure CLI")
            raise
    
    def test_connection(self) -> Dict:
        """
        Test the connection to Azure DevOps and validate authentication.
        
        Performs a test API call to verify that the client can successfully
        connect to Azure DevOps using the configured credentials and organization.
        
        Returns:
            Dict: Test results including:
                - success: Boolean indicating if connection was successful
                - status_code: HTTP status code from the test request
                - message: Descriptive message about the test result
                - organization: Organization name if successful
                - project: Project name if successful
        """
        try:
            # Test with projects endpoint
            url = f"{self.config.BASE_URL}/_apis/projects?api-version={self.config.API_VERSION}"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                projects_data = response.json()
                return {
                    'success': True,
                    'message': f"Successfully connected to ADO. Found {len(projects_data.get('value', []))} projects",
                    'projects': projects_data.get('value', [])
                }
            else:
                return {
                    'success': False,
                    'error': f"Connection failed: {response.status_code} - {response.text}"
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"Connection error: {str(e)}"
            }
    
    def create_work_item(self, title: str, description: str = "", **kwargs) -> Dict:
        """Create a work item in Azure DevOps
        
        Args:
            title: Work item title (required)
            description: Work item description
            **kwargs: Additional fields like area_path, iteration_path, etc.
        
        Returns:
            Dict with success status and work item details or error
        """
        try:
            # Build the JSON patch operations for work item creation
            operations = []
            
            # Title (required field)
            operations.append({
                "op": "add",
                "path": "/fields/System.Title",
                "value": title
            })
            
            # Description (if provided)
            if description:
                operations.append({
                    "op": "add",
                    "path": "/fields/System.Description",
                    "value": description
                })
            
            # Additional fields from kwargs
            field_mappings = {
                'area_path': 'System.AreaPath',
                'iteration_path': 'System.IterationPath',
                'assigned_to': 'System.AssignedTo',
                'customer_scenario': 'Microsoft.VSTS.Common.AcceptanceCriteria',
                'priority': 'Microsoft.VSTS.Common.Priority',
                'tags': 'System.Tags'
            }
            
            for key, value in kwargs.items():
                if key in field_mappings and value:
                    operations.append({
                        "op": "add",
                        "path": f"/fields/{field_mappings[key]}",
                        "value": value
                    })
            
            # Add source tag to identify work items created by this app
            operations.append({
                "op": "add",
                "path": "/fields/System.Tags",
                "value": "IssueTracker;AutoCreated"
            })
            
            # API endpoint for creating work items
            url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/workitems/${self.config.WORK_ITEM_TYPE}?api-version={self.config.API_VERSION}"
            
            # Make the API call
            response = requests.post(url, json=operations, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                work_item = response.json()
                return {
                    'success': True,
                    'work_item_id': work_item['id'],
                    'url': work_item['_links']['html']['href'],
                    'title': work_item['fields']['System.Title'],
                    'state': work_item['fields']['System.State'],
                    'work_item': work_item
                }
            else:
                return {
                    'success': False,
                    'error': f"ADO API Error: {response.status_code} - {response.text}",
                    'url': url
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Request failed: {str(e)}"
            }
    
    def create_work_item_from_issue(self, issue_data: Dict) -> Dict:
        """Create a work item from issue tracker data with custom fields
        
        Args:
            issue_data: Dictionary containing issue information with keys:
                - title: Issue title
                - description: Issue description  
                - impact: Customer impact/scenario
                - opportunity_id: Opportunity ID for tracking
                - milestone_id: Milestone ID for tracking
                - area_path: Area path (optional)
                - iteration_path: Iteration path (optional)
                - priority: Priority level (optional)
        
        Returns:
            Dict with success status and work item details or error
        """
        print("\n" + "="*80)
        print("[ADO] CREATE_WORK_ITEM_FROM_ISSUE - STARTING")
        print("="*80)
        try:
            print("[ADO] STEP 1: Extracting data from issue_data...")
            # Extract data from issue
            title = issue_data.get('title', 'Untitled Issue')
            description = issue_data.get('description', '')
            impact = issue_data.get('impact', '')
            opportunity_id = issue_data.get('opportunity_id', '')
            milestone_id = issue_data.get('milestone_id', '')
            print(f"[ADO] Title: {title[:50]}..." if len(title) > 50 else f"[ADO] Title: {title}")
            print(f"[ADO] Opportunity ID: {opportunity_id}")
            print(f"[ADO] Milestone ID: {milestone_id}")
            
            # Build a comprehensive description including impact
            full_description = description
            if impact:
                full_description += f"\n\n**Customer Impact:**\n{impact}"
            
            print("[ADO] STEP 2: Building JSON patch operations...")
            # Build the JSON patch operations for work item creation with custom fields
            operations = []
            
            # Standard fields
            print("[ADO]   - Adding System.Title")
            operations.append({
                "op": "add",
                "path": "/fields/System.Title",
                "value": title
            })
            
            operations.append({
                "op": "add",
                "path": "/fields/System.Description",
                "value": full_description
            })
            
            # State field - set to 'In Progress'
            operations.append({
                "op": "add",
                "path": "/fields/System.State",
                "value": "In Progress"
            })
            
            # Assigned To field - set to "ACR Accelerate Blockers Help"
            operations.append({
                "op": "add",
                "path": "/fields/System.AssignedTo",
                "value": "ACR Accelerate Blockers Help"
            })
            
            # Custom field: CustomerImpactData (set to Impact statement)
            if impact:
                operations.append({
                    "op": "add",
                    "path": "/fields/custom.CustomerImpactData",
                    "value": impact
                })
            
            # Custom field: CustomerScenarioandDesiredOutcome (formatted AI classification data)
            scenario_data_parts = []
            context_analysis = issue_data.get('context_analysis', {})
            
            print(f"\n[ADO DEBUG] issue_data keys: {list(issue_data.keys())}")
            print(f"[ADO DEBUG] context_analysis: {context_analysis}")
            print(f"[ADO DEBUG] selected_features: {issue_data.get('selected_features', [])}")
            print(f"[ADO DEBUG] selected_uats: {issue_data.get('selected_uats', [])}")
            
            # ⚠️ DEMO FIX (Jan 16 2026): Check BOTH nested and top-level fields
            # ORIGINAL ISSUE: Bot completion card showed blank URL, missing Category/Intent/Classification Reason
            # ROOT CAUSE: Bot sends top-level fields, web app sends nested context_analysis
            # FIX: Check both locations to support both calling patterns
            # This fixes missing classification data in created UAT work items
            category = None
            intent = None
            classification_reason = None
            
            # ⚠️ BUG FIX (Jan 16 2026): Handle None context_analysis properly
            # Previous code called .get() on None causing AttributeError
            if context_analysis and isinstance(context_analysis, dict):
                category = context_analysis.get('category')
                intent = context_analysis.get('intent')
                classification_reason = context_analysis.get('reasoning') or context_analysis.get('classification_reason')
            
            # Fall back to top-level fields if not in context_analysis
            if not category:
                category = issue_data.get('category', 'Unknown')
            if not intent:
                intent = issue_data.get('intent', 'Unknown')
            if not classification_reason:
                classification_reason = issue_data.get('classification_reason', '')
            
            # Add Category and Intent with proper formatting
            if category and category != 'Unknown':
                category_display = category.replace('_', ' ').title()
                scenario_data_parts.append(f"<strong>Category:</strong> {category_display}")
            
            if intent and intent != 'Unknown':
                intent_display = intent.replace('_', ' ').title()
                scenario_data_parts.append(f"<strong>Intent:</strong> {intent_display}")
            
            # Add classification reasoning
            if classification_reason:
                scenario_data_parts.append(f"<strong>Classification Reason:</strong> {classification_reason}")
            
            # Add selected features if present (with links)
            selected_features = issue_data.get('selected_features', [])
            if selected_features:
                feature_links = []
                for feature_id in selected_features:
                    # Create ADO link format: <a href="URL">ID</a>
                    feature_url = f"https://dev.azure.com/unifiedactiontracker/Technical%20Feedback/_workitems/edit/{feature_id}"
                    feature_links.append(f'<a href="{feature_url}" target="_blank">#{feature_id}</a>')
                feature_html = ', '.join(feature_links)
                scenario_data_parts.append(f"<strong>Associated Features:</strong> {feature_html}")
            
            # Add selected related UATs if present (with links)
            selected_uats = issue_data.get('selected_uats', [])
            if selected_uats:
                uat_links = []
                for uat_id in selected_uats:
                    # Create ADO link format: <a href="URL">ID</a>
                    uat_url = f"https://dev.azure.com/unifiedactiontracker/Unified%20Action%20Tracker/_workitems/edit/{uat_id}"
                    uat_links.append(f'<a href="{uat_url}" target="_blank">#{uat_id}</a>')
                uat_html = ', '.join(uat_links)
                scenario_data_parts.append(f"<strong>Associated UATs:</strong> {uat_html}")
            
            if scenario_data_parts:
                # Join with <br><br> for proper HTML line breaks in Azure DevOps
                scenario_value = "<br><br>".join(scenario_data_parts)
                print(f"\n[ADO DEBUG] Writing to CustomerScenarioandDesiredOutcome:")
                print(f"[ADO DEBUG] Value: {scenario_value}")
                operations.append({
                    "op": "add",
                    "path": "/fields/custom.CustomerScenarioandDesiredOutcome",
                    "value": scenario_value
                })
            else:
                print("[ADO DEBUG] ⚠️ No scenario_data_parts to write!")
            
            # Custom field: AssigntoCorp (set to True)
            operations.append({
                "op": "add",
                "path": "/fields/custom.AssigntoCorp",
                "value": True
            })
            
            # Custom field: Opportunity_ID (set to submitted Opportunity Number)
            if opportunity_id:
                operations.append({
                    "op": "add",
                    "path": "/fields/custom.Opportunity_ID",
                    "value": opportunity_id
                })
            
            # Custom field: MilestoneID (set to submitted Milestone ID)
            if milestone_id:
                operations.append({
                    "op": "add",
                    "path": "/fields/custom.MilestoneID",
                    "value": milestone_id
                })
            
            # Custom fields (StatusUpdate, pChallengeDetails) are applied
            # via a separate PATCH after creation so that orgs without these
            # custom fields still get the work item created successfully.
            custom_field_ops = []
            custom_field_ops.append({
                "op": "add",
                "path": "/fields/Custom.StatusUpdate",
                "value": "WizardAuto"
            })
            evaluation_html = issue_data.get('evaluation_summary_html', '')
            if evaluation_html:
                custom_field_ops.append({
                    "op": "add",
                    "path": "/fields/Custom.pChallengeDetails",
                    "value": evaluation_html
                })
            
            # Add source tag to identify work items created by this app
            operations.append({
                "op": "add",
                "path": "/fields/System.Tags",
                "value": "IssueTracker;AutoCreated;WizardGenerated"
            })
            
            # Add optional fields if provided
            if issue_data.get('area_path'):
                operations.append({
                    "op": "add",
                    "path": "/fields/System.AreaPath",
                    "value": issue_data['area_path']
                })
            
            if issue_data.get('iteration_path'):
                operations.append({
                    "op": "add",
                    "path": "/fields/System.IterationPath",
                    "value": issue_data['iteration_path']
                })
            
            if issue_data.get('priority'):
                operations.append({
                    "op": "add",
                    "path": "/fields/Microsoft.VSTS.Common.Priority",
                    "value": issue_data['priority']
                })
            
            print(f"[ADO] STEP 3: Total operations built: {len(operations)}")
            
            # API endpoint for creating work items
            url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/workitems/${self.config.WORK_ITEM_TYPE}?api-version={self.config.API_VERSION}"
            
            print(f"[ADO] STEP 4: Getting fresh authentication headers...")
            # Get fresh headers with new token (tokens expire after 1 hour)
            try:
                headers = self._get_headers()
                print(f"[ADO]   ✓ Headers obtained successfully")
            except Exception as header_error:
                print(f"[ADO]   ❌ FAILED to get headers: {header_error}")
                raise
            
            print(f"[ADO] STEP 5: Making POST request to Azure DevOps...")
            print(f"[ADO]   URL: {url}")
            print(f"[ADO]   Operations: {len(operations)} items")
            print(f"[ADO]   Headers: Content-Type={headers.get('Content-Type')}, Auth=Bearer ***")
            
            # Make the API call
            response = requests.post(url, json=operations, headers=headers, timeout=30)
            
            print(f"[ADO] STEP 6: Response received")
            print(f"[ADO]   Status Code: {response.status_code}")
            print(f"[ADO]   Status Text: {response.reason}")
            
            if response.status_code == 200:
                print(f"[ADO] STEP 7: Success! Parsing response JSON...")
                work_item = response.json()
                work_item_id = work_item['id']
                print(f"[ADO]   ✓ Work item created: ID {work_item_id}")

                # Best-effort: PATCH custom fields onto the new work item.
                # If the org doesn't have these fields, log and move on.
                if custom_field_ops:
                    try:
                        patch_url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/workitems/{work_item_id}?api-version={self.config.API_VERSION}"
                        patch_resp = requests.patch(patch_url, json=custom_field_ops, headers=headers)
                        if patch_resp.status_code == 200:
                            print(f"[ADO]   ✓ Custom fields applied successfully")
                        else:
                            print(f"[ADO]   ⚠️ Custom fields PATCH returned {patch_resp.status_code} — skipping (work item still created)")
                            print(f"[ADO]     Response: {patch_resp.text[:300]}")
                    except Exception as patch_err:
                        print(f"[ADO]   ⚠️ Custom fields PATCH failed: {patch_err} — skipping")

                print("="*80)
                return {
                    'success': True,
                    'work_item_id': work_item['id'],
                    'url': work_item['_links']['html']['href'],
                    'title': work_item['fields']['System.Title'],
                    'state': work_item['fields']['System.State'],
                    'assigned_to': work_item['fields'].get('System.AssignedTo', {}).get('displayName', 'ACR Accelerate Blockers Help'),
                    'opportunity_id': opportunity_id,
                    'milestone_id': milestone_id,
                    'work_item': work_item,
                    'source': 'IssueTracker',
                    'original_issue': issue_data
                }
            else:
                print(f"[ADO] STEP 7: ❌ ERROR - Non-200 status code")
                print(f"[ADO]   Status: {response.status_code} ({response.reason})")
                print(f"[ADO]   Response content type: {response.headers.get('Content-Type')}")
                print(f"[ADO]   Response length: {len(response.text)} bytes")
                print(f"[ADO]   First 500 chars of response: {response.text[:500]}")
                
                # Try to parse JSON error for better message
                error_msg = f"Status {response.status_code}"
                try:
                    print(f"[ADO]   Attempting to parse JSON error response...")
                    error_json = response.json()
                    print(f"[ADO]   JSON keys: {list(error_json.keys())}")
                    if 'message' in error_json:
                        error_msg = error_json['message']
                        print(f"[ADO]   Found 'message': {error_msg}")
                    elif 'value' in error_json and isinstance(error_json['value'], dict):
                        error_msg = error_json['value'].get('Message', error_msg)
                        print(f"[ADO]   Found 'value.Message': {error_msg}")
                except Exception as parse_error:
                    print(f"[ADO]   ⚠️ Could not parse as JSON: {parse_error}")
                    error_msg = response.text[:200]  # First 200 chars of raw response
                
                print("="*80)
                return {
                    'success': False,
                    'error': f"Azure DevOps API Error ({response.status_code}): {error_msg}",
                    'url': url
                }
                
        except Exception as e:
            print(f"[ADO] ❌ EXCEPTION in create_work_item_from_issue: {type(e).__name__}")
            print(f"[ADO] Exception message: {str(e)}")
            import traceback
            print(f"[ADO] Traceback:")
            traceback.print_exc()
            print("="*80)
            return {
                'success': False,
                'error': f"Failed to create work item from issue data: {str(e)}"
            }
    
    def get_work_item(self, work_item_id: int) -> Dict:
        """
        Retrieve a work item by ID.
        
        Args:
            work_item_id: The ID of the work item to retrieve
            
        Returns:
            Dict with work item data or error information
        """
        try:
            url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/workitems/{work_item_id}?api-version={self.config.API_VERSION}"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    'error': f"Failed to retrieve work item: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            return {
                'error': f"Failed to retrieve work item: {str(e)}"
            }
    
    def query_work_items(self, work_item_type: str = "Actions", state: Optional[str] = None, 
                        assigned_to: Optional[str] = None, max_results: int = 50) -> list:
        """
        Query work items with optional filters.
        
        Args:
            work_item_type: Type of work items to query (default: "Actions")
            state: Filter by state (optional)
            assigned_to: Filter by assignee (optional)
            max_results: Maximum number of results to return
            
        Returns:
            List of work items matching the criteria
        """
        try:
            # Build WIQL query
            query = f"SELECT [System.Id], [System.Title], [System.State], [System.CreatedDate], [System.AssignedTo] FROM WorkItems WHERE [System.TeamProject] = '{self.config.PROJECT}' AND [System.WorkItemType] = '{work_item_type}'"
            
            if state:
                query += f" AND [System.State] = '{state}'"
            if assigned_to:
                query += f" AND [System.AssignedTo] = '{assigned_to}'"
                
            query += f" ORDER BY [System.CreatedDate] DESC"
            
            # Execute WIQL query
            wiql_url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/wiql?api-version={self.config.API_VERSION}"
            wiql_response = requests.post(wiql_url, json={"query": query}, headers=self.headers, timeout=30)
            
            if wiql_response.status_code != 200:
                return []
            
            wiql_result = wiql_response.json()
            work_item_ids = [item['id'] for item in wiql_result.get('workItems', [])][:max_results]
            
            if not work_item_ids:
                return []
            
            # Get full work item details
            ids_param = ",".join(str(id) for id in work_item_ids)
            details_url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/workitems?ids={ids_param}&api-version={self.config.API_VERSION}"
            details_response = requests.get(details_url, headers=self.headers, timeout=30)
            
            if details_response.status_code == 200:
                return details_response.json().get('value', [])
            else:
                return []
                
        except Exception as e:
            print(f"Error querying work items: {e}")
            return []
    
    def update_work_item(self, work_item_id: int, updates: Dict[str, Any]) -> Dict:
        """
        Update a work item with the specified field changes.
        
        Args:
            work_item_id: The ID of the work item to update
            updates: Dictionary of field names to new values
            
        Returns:
            Dict with success status and updated work item details
        """
        try:
            # Build JSON Patch operations
            operations = []
            for field, value in updates.items():
                # Ensure field has proper path format
                if not field.startswith("/fields/"):
                    if not field.startswith("System.") and not field.startswith("Custom.") and not field.startswith("Microsoft."):
                        field = f"System.{field}"
                    field = f"/fields/{field}"
                else:
                    # Strip /fields/ prefix if present, we'll add it back
                    field = field.replace("/fields/", "")
                    if not field.startswith("System.") and not field.startswith("Custom.") and not field.startswith("Microsoft."):
                        field = f"System.{field}"
                    field = f"/fields/{field}"
                    
                operations.append({
                    "op": "add",
                    "path": field,
                    "value": value
                })
            
            url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/workitems/{work_item_id}?api-version={self.config.API_VERSION}"
            
            response = requests.patch(url, json=operations, headers=self.headers)
            
            if response.status_code == 200:
                work_item = response.json()
                return {
                    'success': True,
                    'work_item_id': work_item['id'],
                    'work_item': work_item
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to update work item: {response.status_code} - {response.text}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to update work item: {str(e)}"
            }
    
    def get_work_item_fields(self) -> Dict:
        try:
            url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/workitemtypes/{self.config.WORK_ITEM_TYPE}?api-version={self.config.API_VERSION}"
            
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                work_item_type = response.json()
                return {
                    'success': True,
                    'fields': work_item_type.get('fields', []),
                    'work_item_type': work_item_type
                }
            else:
                return {
                    'success': False,
                    'error': f"Failed to get work item type: {response.status_code} - {response.text}"
                }
        except Exception as e:
            return {
                'success': False,
                'error': f"Request failed: {str(e)}"
            }
    
    def search_tft_features(self, title: str, description: str, threshold: float = 0.7, azure_services: list = None) -> List[Dict]:
        """
        Search Technical Feedback ADO for similar Features.
        """
        _D = "[TFT-DEBUG]"  # prefix for easy grep
        print(f"\n{'='*80}")
        print(f"{_D} ===== search_tft_features() START =====")
        print(f"{_D} Title:          {repr(title[:120])}")
        print(f"{_D} Desc len:       {len(description) if description else 0}")
        print(f"{_D} Threshold:      {threshold}")
        print(f"{_D} azure_services: {azure_services}")
        print(f"{'='*80}")
        try:
            from datetime import datetime, timedelta
            
            # Search Technical Feedback organization — read from config
            try:
                from config import get_app_config as _gcfg
                _cfg = _gcfg()
                tft_org = _cfg.ado_tft_organization
                tft_project = _cfg.ado_tft_project
            except Exception:
                tft_org = "unifiedactiontracker"
                tft_project = "Technical Feedback"
            tft_base_url = f"https://dev.azure.com/{tft_org}"
            print(f"{_D} Step 1: org={tft_org}, project={tft_project}, base_url={tft_base_url}")
            
            # Get token for TFT org using InteractiveBrowserCredential
            credential = self.config.get_tft_credential()
            token = credential.get_token(self.config.ADO_SCOPE).token
            tft_headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            print(f"{_D} Step 2: Auth token obtained (len={len(token)})")
            
            # Search last 24 months
            cutoff_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
            print(f"{_D} Step 3: Cutoff date = {cutoff_date} (730 days)")
            
            # ── SERVICE NAME RESOLUTION VIA SERVICETREE ──
            import re
            import json
            import os

            candidate_names: list = []

            # Source A: AI-detected azure_services (most reliable)
            if azure_services:
                candidate_names.extend(s.strip() for s in azure_services if s.strip())
                print(f"{_D} Step 4a: AI-detected service names: {candidate_names}")
            else:
                print(f"{_D} Step 4a: No AI-detected azure_services provided")

            # Source B: Extract "Azure/Microsoft <Service>" patterns from title
            azure_pattern = re.compile(
                r'(?:Azure|Microsoft)\s+((?:[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*))', re.IGNORECASE
            )
            regex_matches = []
            for m in azure_pattern.finditer(title):
                name = m.group(1).strip()
                if name and name not in candidate_names:
                    candidate_names.append(name)
                    regex_matches.append(name)
            print(f"{_D} Step 4b: Regex-extracted from title: {regex_matches}")

            # Source C: Parenthesised abbreviations like "(APIM)", "(AKS)"
            abbr_matches = []
            for abbr in re.findall(r'\(([A-Z]{2,8})\)', title):
                if abbr not in candidate_names:
                    candidate_names.append(abbr)
                    abbr_matches.append(abbr)
            print(f"{_D} Step 4c: Abbreviations from title: {abbr_matches}")
            print(f"{_D} Step 4 TOTAL candidate_names: {candidate_names}")

            # ── Resolve candidates via ServiceTree ──
            from servicetree_service import get_servicetree_service
            svc_tree = get_servicetree_service()

            resolved_services = svc_tree.lookup_services(candidate_names) if candidate_names else []
            print(f"{_D} Step 5: ServiceTree resolved {len(resolved_services)} services:")
            for i, svc in enumerate(resolved_services):
                print(f"{_D}   [{i}] name={repr(svc.get('name',''))} offering={repr(svc.get('offering',''))}")

            # ── Build WIQL search terms from ServiceTree results ──
            search_terms: list = []
            for svc in resolved_services:
                svc_name = svc.get("name", "")
                offering = svc.get("offering", "")
                if svc_name and svc_name not in search_terms:
                    search_terms.append(svc_name)
                if offering and offering != svc_name and offering not in search_terms:
                    search_terms.append(offering)
                inner = re.findall(r'\(([A-Z][A-Za-z0-9 ]+)\)', svc_name)
                for abbr in inner:
                    if abbr not in search_terms:
                        search_terms.append(abbr)
                for cand in candidate_names:
                    if cand not in search_terms and cand.lower() in svc_name.lower():
                        search_terms.append(cand)

            # Fallback: if ServiceTree had no matches, use title keywords
            if not search_terms:
                print(f"{_D} Step 6: No ServiceTree matches — falling back to title keywords")
                title_words = re.findall(r'\b[A-Za-z]{4,}\b', title)
                noise = {'support', 'request', 'feature', 'provide', 'need', 'customer',
                         'blocked', 'sale', 'seats', 'services', 'service', 'azure',
                         'microsoft', 'please', 'help', 'want', 'would', 'could',
                         'should', 'with', 'from', 'that', 'this', 'have', 'been'}
                meaningful = [w for w in title_words if w.lower() not in noise]
                print(f"{_D} Step 6: title_words={title_words}, meaningful={meaningful}")
                if meaningful:
                    search_terms.append(meaningful[0])
            else:
                print(f"{_D} Step 6: search_terms from ServiceTree: {search_terms}")

            # Build WIQL product filter (OR across all terms)
            if search_terms:
                clauses = " OR ".join(
                    f"[System.Title] CONTAINS '{term}'" for term in search_terms
                )
                product_filter = f"AND ({clauses})"
                print(f"{_D} Step 7: Multi-term WIQL filter ({len(search_terms)} terms): {product_filter}")
            else:
                product_filter = ""
                print(f"{_D} Step 7: No filter terms — running broad WIQL query")
            wiql_query = f"""
            SELECT [System.Id], [System.Title], [System.Description], [System.ChangedDate], [System.State]
            FROM workitems
            WHERE [System.TeamProject] = '{tft_project}'
            AND [System.WorkItemType] = 'Feature'
            AND [System.ChangedDate] >= '{cutoff_date}'
            AND [System.State] <> 'Closed'
            {product_filter}
            ORDER BY [System.ChangedDate] DESC
            """
            
            print(f"{_D} Step 8: WIQL Query:\n{wiql_query.strip()}")
            
            wiql_url = f"{tft_base_url}/{quote(tft_project)}/_apis/wit/wiql?api-version={self.config.API_VERSION}&$top=50"
            print(f"{_D} Step 9: POST {wiql_url}")
            wiql_response = requests.post(
                wiql_url,
                headers=tft_headers,
                json={'query': wiql_query},
                timeout=30
            )
            
            print(f"{_D} Step 10: WIQL response status={wiql_response.status_code}")
            if wiql_response.status_code != 200:
                try:
                    err_body = wiql_response.json()
                except Exception:
                    err_body = wiql_response.text[:500]
                print(f"{_D} Step 10: ERROR body: {err_body}")
                print(f"{_D} ===== search_tft_features() END (WIQL error) =====")
                return []
            
            work_items = wiql_response.json().get('workItems', [])
            if not work_items:
                print(f"{_D} Step 10: No Features found — returning []")
                print(f"{_D} ===== search_tft_features() END (0 WIQL results) =====")
                return []
            
            print(f"{_D} Step 10: WIQL returned {len(work_items)} Feature IDs")
            print(f"{_D} Step 10: First 5 IDs: {[wi.get('id') for wi in work_items[:5]]}")
            
            # Get detailed work item info (limit to 200 since we have product-filtered results)
            work_item_ids = [str(wi['id']) for wi in work_items[:50]]
            batch_url = f"{tft_base_url}/{quote(tft_project)}/_apis/wit/workitemsbatch?api-version={self.config.API_VERSION}"
            
            print(f"{_D} Step 11: Batch-fetching {len(work_item_ids)} items from {batch_url}")
            batch_response = requests.post(
                batch_url,
                headers=tft_headers,
                json={
                    'ids': work_item_ids,
                    'fields': ['System.Id', 'System.Title', 'System.Description', 'System.State', 'System.CreatedDate']
                },
                timeout=30
            )
            
            print(f"{_D} Step 12: Batch response status={batch_response.status_code}")
            if batch_response.status_code != 200:
                print(f"{_D} Step 12: Batch request FAILED")
                print(f"{_D} ===== search_tft_features() END (batch error) =====")
                return []
            
            # Parse all items first (shared by both AI and fallback paths)
            all_items = batch_response.json().get('value', [])
            print(f"{_D} Step 13: Batch returned {len(all_items)} items")
            
            # Limit items for embedding comparison — each item requires
            # an individual Azure OpenAI embedding call, so keep this small.
            if len(all_items) > 20:
                print(f"{_D} Step 13: Limiting from {len(all_items)} to 20 features (embedding budget)")
                all_items = all_items[:20]
            
            parsed_items = []
            for item in all_items:
                fields = item.get('fields', {})
                item_id = fields.get('System.Id')
                item_title = fields.get('System.Title', '')
                item_desc = fields.get('System.Description', '')
                
                # Strip HTML tags from description
                if item_desc:
                    from html import unescape
                    import re as _re
                    item_desc = _re.sub(r'<[^>]+>', '', item_desc)
                    item_desc = unescape(item_desc)
                    item_desc = ' '.join(item_desc.split())
                
                parsed_items.append({
                    'id': item_id,
                    'title': item_title,
                    'description': item_desc,
                    'state': fields.get('System.State', 'Unknown'),
                    'created_date': fields.get('System.CreatedDate', ''),
                    'url': f"{tft_base_url}/{quote(tft_project)}/_workitems/edit/{item_id}",
                    'source': 'Technical Feedback'
                })
            
            # Score features using keyword overlap + SequenceMatcher (no embeddings — too slow / rate-limited)
            print(f"{_D} Step 14: Scoring {len(parsed_items)} features via keyword + SequenceMatcher...")
            import re as _re
            from difflib import SequenceMatcher

            search_text = f"{title} {description}".lower()
            search_words = set(_re.findall(r'\b[a-z]{3,}\b', search_text))
            stop_words = {'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was',
                          'will', 'has', 'have', 'been', 'not', 'but', 'they', 'their',
                          'them', 'which', 'when', 'what', 'where', 'who', 'how', 'all',
                          'can', 'would', 'could', 'should', 'into', 'also', 'than',
                          'customer', 'services', 'service', 'support', 'request', 'feature',
                          'new', 'need', 'sale', 'seats', 'blocked', 'related', 'requires'}
            search_words -= stop_words
            search_title_lower = title.lower()
            print(f"{_D} Step 14: search_words ({len(search_words)}): {sorted(list(search_words))[:15]}")

            matches = []
            for p_item in parsed_items:
                feature_text = f"{p_item['title']} {p_item['description']}".lower()
                feature_words = set(_re.findall(r'\b[a-z]{3,}\b', feature_text))
                feature_words -= stop_words

                # Keyword overlap score
                if search_words and feature_words:
                    common = search_words & feature_words
                    overlap = len(common) / min(len(search_words), len(feature_words))
                else:
                    overlap = 0.0

                # SequenceMatcher on titles (more precise)
                seq_sim = SequenceMatcher(None, search_title_lower, p_item['title'].lower()).ratio()

                # Combined score: weight title similarity higher
                score = (seq_sim * 0.6) + (overlap * 0.4)

                passed = score >= 0.15 or len(parsed_items) <= 10
                print(f"{_D}   id={p_item['id']} score={score:.3f} (seq={seq_sim:.3f} ovl={overlap:.3f}) {'✓' if passed else '✗'} title={repr(p_item['title'][:60])}")

                if passed:
                    matches.append({
                        **p_item,
                        'similarity': round(min(score, 0.99), 2),
                    })

            matches.sort(key=lambda x: x['similarity'], reverse=True)
            print(f"{_D} Step 15: Found {len(matches)} features above threshold")
            if matches:
                for i, m in enumerate(matches[:5]):
                    print(f"{_D}   match[{i}] id={m['id']} sim={m['similarity']} title={repr(m['title'][:60])}")
            print(f"{_D} ===== search_tft_features() END — {len(matches[:10])} results =====")
            return matches[:10]
            
        except Exception as e:
            print(f"{_D} CRITICAL ERROR: {e}")
            import traceback
            print(f"{_D} Traceback:\n{traceback.format_exc()}")
            print(f"{_D} ===== search_tft_features() END (exception) =====")
            return []


def test_ado_integration():
    """Test function to verify ADO integration works"""
    print("Testing Azure DevOps Integration...")
    
    # Initialize client
    ado_client = AzureDevOpsClient()
    
    # Test connection
    print("\n1. Testing connection...")
    connection_result = ado_client.test_connection()
    if connection_result['success']:
        print(f"✓ {connection_result['message']}")
    else:
        print(f"✗ {connection_result['error']}")
        return
    
    # Test work item creation
    print("\n2. Testing work item creation...")
    test_work_item = ado_client.create_work_item(
        title="Test Work Item from Issue Tracker",
        description="This is a test work item created by the Issue Tracker application to verify ADO integration.",
        customer_scenario="Testing the integration between Issue Tracker and Azure DevOps"
    )
    
    if test_work_item['success']:
        print(f"✓ Work item created successfully!")
        print(f"  - ID: {test_work_item['work_item_id']}")
        print(f"  - Title: {test_work_item['title']}")
        print(f"  - State: {test_work_item['state']}")
        print(f"  - URL: {test_work_item['url']}")
    else:
        print(f"✗ Failed to create work item: {test_work_item['error']}")
    
    # Test getting work item fields
    print("\n3. Testing work item field retrieval...")
    fields_result = ado_client.get_work_item_fields()
    if fields_result['success']:
        print(f"✓ Retrieved work item type information")
        print(f"  - Available fields: {len(fields_result['fields'])}")
    else:
        print(f"✗ Failed to get work item fields: {fields_result['error']}")


if __name__ == "__main__":
    test_ado_integration()
