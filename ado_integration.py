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
    ORGANIZATION = "unifiedactiontrackertest"
    PROJECT = "Unified Action Tracker Test"
    BASE_URL = f"https://dev.azure.com/{ORGANIZATION}"
    API_VERSION = "7.0"
    WORK_ITEM_TYPE = "Action"  # Custom work item type
    
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

        # 2. Interactive Browser with persistent disk cache
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
    def get_tft_credential():
        """
        Get Azure credential for Technical Feedback organization access.
        The TFT org (unifiedactiontracker) lives in the Microsoft tenant,
        so we need a credential scoped to that tenant — NOT the shared
        credential which targets the OpenAI tenant.

        Auth chain (in order):
        1. ManagedIdentityCredential — if ADO_MANAGED_IDENTITY_CLIENT_ID is set
           (same identity works for both orgs once registered in ADO)
        2. AzureCliCredential — if logged into Microsoft tenant
        3. InteractiveBrowserCredential with Microsoft tenant_id

        Returns:
            Azure credential object configured for TFT org access
        """
        # Return cached credential if available
        if AzureDevOpsConfig._cached_tft_credential is not None:
            print("[AUTH] Reusing cached TFT credential...")
            return AzureDevOpsConfig._cached_tft_credential

        # 1. Managed Identity — for container/cloud deployment
        # Falls back to AZURE_CLIENT_ID (same reasoning as get_credential above)
        ado_mi_client_id = os.environ.get("ADO_MANAGED_IDENTITY_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID")
        if ado_mi_client_id:
            print(f"[AUTH] Trying Managed Identity credential for TFT (client_id={ado_mi_client_id[:8]}...)...")
            try:
                from azure.identity import ManagedIdentityCredential
                credential = ManagedIdentityCredential(client_id=ado_mi_client_id)
                credential.get_token(AzureDevOpsConfig.ADO_SCOPE)
                AzureDevOpsConfig._cached_tft_credential = credential
                print("[SUCCESS] Managed Identity authentication successful for TFT")
                return credential
            except Exception as mi_error:
                print(f"[WARNING] Managed Identity TFT credential failed: {mi_error}")
                print("[INFO] Falling back to other auth methods...")

        # 2. Try Azure CLI (if logged into Microsoft tenant)
        import subprocess
        MICROSOFT_TENANT = "72f988bf-86f1-41af-91ab-2d7cd011db47"

        try:
            result = subprocess.run(
                ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0:
                cli_tenant = result.stdout.strip()
                if cli_tenant == MICROSOFT_TENANT:
                    from azure.identity import AzureCliCredential
                    credential = AzureCliCredential()
                    credential.get_token(AzureDevOpsConfig.ADO_SCOPE)
                    AzureDevOpsConfig._cached_tft_credential = credential
                    print("[AUTH] Using Azure CLI credential for TFT (Microsoft tenant)")
                    return credential
                else:
                    print(f"[AUTH] CLI tenant {cli_tenant} != Microsoft tenant, using browser")
        except Exception:
            pass

        # 2b. Try SharedTokenCache — picks up a previous browser login
        TFT_CACHE_NAME = "gcs-ado-tft-auth"
        try:
            from azure.identity import SharedTokenCacheCredential, TokenCachePersistenceOptions
            cache_opts = TokenCachePersistenceOptions(name=TFT_CACHE_NAME)
            print("[AUTH] Checking persistent token cache for TFT...")
            shared_cred = SharedTokenCacheCredential(
                tenant_id=MICROSOFT_TENANT,
                cache_persistence_options=cache_opts,
            )
            shared_cred.get_token(AzureDevOpsConfig.ADO_SCOPE)
            AzureDevOpsConfig._cached_tft_credential = shared_cred
            print("[AUTH] TFT persistent cache hit — no browser prompt needed")
            return shared_cred
        except Exception as cache_err:
            print(f"[AUTH] No usable cached TFT token ({cache_err})")

        # 3. Interactive Browser with Microsoft tenant ID
        # Persistent cache: token survives server restarts / uvicorn --reload
        from azure.identity import InteractiveBrowserCredential, TokenCachePersistenceOptions
        cache_opts = TokenCachePersistenceOptions(name=TFT_CACHE_NAME)
        print("[AUTH] Creating TFT credential via browser (Microsoft tenant, persistent cache)...")
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
            
            response = requests.get(url, headers=self.headers)
            
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
            response = requests.post(url, json=operations, headers=self.headers)
            
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
                    feature_url = f"https://dev.azure.com/acrblockers/b47dfa86-3c5d-4fc9-8ab9-e4e10ec93dc4/_workitems/edit/{feature_id}"
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
            
            # Custom field: StatusUpdate (set to 'WizardAuto')
            # Uses Custom.StatusUpdate — must match the production ADO org
            operations.append({
                "op": "add",
                "path": "/fields/Custom.StatusUpdate",
                "value": "WizardAuto"
            })

            # Custom field: pChallengeDetails (AI evaluation summary HTML)
            # Uses Custom.pChallengeDetails — the 'p' prefix matches the
            # production ADO org field definition and triage/services/ado_writer.py.
            evaluation_html = issue_data.get('evaluation_summary_html', '')
            if evaluation_html:
                operations.append({
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
            response = requests.post(url, json=operations, headers=headers)
            
            print(f"[ADO] STEP 6: Response received")
            print(f"[ADO]   Status Code: {response.status_code}")
            print(f"[ADO]   Status Text: {response.reason}")
            
            # If we get TF51535 "Cannot find field custom.X", strip that field
            # and retry.  The test org may not have all custom fields defined.
            if response.status_code == 400 and 'TF51535' in response.text:
                import re as _re
                missing = _re.search(r'Cannot find field (\S+)', response.text)
                if missing:
                    bad_field = missing.group(1)
                    print(f"[ADO]   ⚠️ Custom field '{bad_field}' not found — retrying without it")
                    operations = [
                        op for op in operations
                        if not op.get("path", "").endswith(bad_field)
                    ]
                    response = requests.post(url, json=operations, headers=headers)
                    print(f"[ADO]   Retry status: {response.status_code}")
                    # If another custom field is also missing, strip and retry once more
                    if response.status_code == 400 and 'TF51535' in response.text:
                        missing2 = _re.search(r'Cannot find field (\S+)', response.text)
                        if missing2:
                            bad_field2 = missing2.group(1)
                            print(f"[ADO]   ⚠️ Custom field '{bad_field2}' also missing — retrying")
                            operations = [
                                op for op in operations
                                if not op.get("path", "").endswith(bad_field2)
                            ]
                            response = requests.post(url, json=operations, headers=headers)
            
            if response.status_code == 200:
                print(f"[ADO] STEP 7: Success! Parsing response JSON...")
                work_item = response.json()
                print(f"[ADO]   ✓ Work item created: ID {work_item['id']}")
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
            
            response = requests.get(url, headers=self.headers)
            
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
            wiql_response = requests.post(wiql_url, json={"query": query}, headers=self.headers)
            
            if wiql_response.status_code != 200:
                return []
            
            wiql_result = wiql_response.json()
            work_item_ids = [item['id'] for item in wiql_result.get('workItems', [])][:max_results]
            
            if not work_item_ids:
                return []
            
            # Get full work item details
            ids_param = ",".join(str(id) for id in work_item_ids)
            details_url = f"{self.config.BASE_URL}/{quote(self.config.PROJECT)}/_apis/wit/workitems?ids={ids_param}&api-version={self.config.API_VERSION}"
            details_response = requests.get(details_url, headers=self.headers)
            
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
            
            response = requests.get(url, headers=self.headers)
            
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
        
        Searches the Technical Feedback project for existing Feature work items
        that match the provided title and description.
        
        Args:
            title: Issue title to search for
            description: Issue description for matching
            threshold: Similarity threshold (0.0-1.0), default 0.7
            azure_services: List of Azure service names from AI analysis (preferred over regex)
            
        Returns:
            List of matching features with metadata and similarity scores
        """
        try:
            from datetime import datetime, timedelta
            
            # Search Technical Feedback organization
            tft_org = "unifiedactiontracker"
            tft_project = "Technical Feedback"
            tft_base_url = f"https://dev.azure.com/{tft_org}"
            
            # Get token for TFT org using InteractiveBrowserCredential
            # This will open a browser window for authentication on first use
            credential = self.config.get_tft_credential()
            token = credential.get_token(self.config.ADO_SCOPE).token
            tft_headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Search last 24 months (expanded from 12 to capture older features)
            cutoff_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
            
            # SMART SERVICE NAME EXTRACTION & PROGRESSIVE SEARCH
            # Step 1: Prefer AI-detected azure_services from domain_entities
            import re
            import json
            import os
            
            base_service_name = None
            
            # Priority 1: Use azure_services from AI analysis (most reliable)
            if azure_services:
                # Use the first detected Azure service name
                base_service_name = azure_services[0].strip()
                print(f"[TFT Search] Using AI-detected service name: {base_service_name}")
            
            # Priority 2: Try to extract "Azure ServiceName" or "Microsoft ServiceName"
            if not base_service_name:
                azure_service_pattern = r'(?:Azure|Microsoft)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
                azure_match = re.search(azure_service_pattern, title)
                
                if azure_match:
                    base_service_name = azure_match.group(1).strip()
                    print(f"[TFT Search] Extracted service name (with Azure prefix): {base_service_name}")
            
            # Priority 3: Find 2-word capitalized phrases (use FIRST, not last)
            if not base_service_name:
                service_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
                # Filter out common non-service phrases
                noise_words = {'Blocked Sale', 'Kelly Services', 'Session Windows',
                               'New Feature', 'Feature Request', 'Support Request',
                               'Please Help', 'Need Help', 'High Priority'}
                potential_services = [
                    m for m in re.findall(service_pattern, title)
                    if m not in noise_words
                ]
                
                if potential_services:
                    # Use the FIRST found service name (most likely to be the actual service)
                    base_service_name = potential_services[0].strip()
                    print(f"[TFT Search] Extracted service name: {base_service_name}")
            
            # Priority 4: Look for known TFT product keywords in title
            if not base_service_name:
                _known_tft_products = {
                    'cycle cloud': 'Cycle Cloud', 'cyclecloud': 'CycleCloud',
                    'redhat': 'Redhat', 'red hat': 'Red Hat',
                    'openshift': 'OpenShift', 'rhel': 'RHEL',
                    'kubernetes': 'Kubernetes', 'aks': 'AKS',
                    'databricks': 'Databricks', 'fabric': 'Fabric',
                    'synapse': 'Synapse', 'purview': 'Purview',
                    'sentinel': 'Sentinel', 'defender': 'Defender',
                    'intune': 'Intune', 'autopilot': 'Autopilot',
                    'devops': 'DevOps', 'cosmos': 'Cosmos',
                    'postgresql': 'PostgreSQL', 'mysql': 'MySQL',
                    'sql server': 'SQL Server', 'sql managed': 'SQL Managed',
                    'virtual desktop': 'Virtual Desktop', 'avd': 'AVD',
                    'private access': 'Private Access',
                    'global secure access': 'Global Secure Access',
                    'entra': 'Entra', 'active directory': 'Active Directory',
                    'key vault': 'Key Vault', 'keyvault': 'KeyVault',
                    'storage account': 'Storage', 'blob storage': 'Blob',
                    'app service': 'App Service', 'functions': 'Functions',
                    'logic apps': 'Logic Apps', 'event grid': 'Event Grid',
                    'service bus': 'Service Bus', 'iot hub': 'IoT Hub',
                    'iot edge': 'IoT Edge', 'iot central': 'IoT Central',
                    'machine learning': 'Machine Learning',
                    'cognitive': 'Cognitive', 'openai': 'OpenAI',
                    'power bi': 'Power BI', 'power automate': 'Power Automate',
                    'sharepoint': 'SharePoint', 'teams': 'Teams',
                    'copilot': 'Copilot', 'windows 365': 'Windows 365',
                    'hpc': 'HPC', 'batch': 'Batch',
                    'marketplace': 'Marketplace', 'monitor': 'Monitor',
                    'load balancer': 'Load Balancer', 'firewall': 'Firewall',
                    'front door': 'Front Door', 'cdn': 'CDN',
                    'route server': 'Route Server', 'expressroute': 'ExpressRoute',
                    'vpn gateway': 'VPN Gateway', 'bastion': 'Bastion',
                    'arc': 'Arc', 'stack hci': 'Stack HCI',
                    'vmware': 'VMware', 'sap': 'SAP', 'oracle': 'Oracle',
                }
                title_lower = title.lower()
                for keyword, display_name in sorted(_known_tft_products.items(), key=lambda x: len(x[0]), reverse=True):
                    if keyword in title_lower:
                        base_service_name = display_name
                        print(f"[TFT Search] Matched known product: {base_service_name}")
                        break

            if not base_service_name:
                print("[TFT Search] No service name found, using broad keyword search from title")
                # Use the most meaningful words from the title as a search filter
                import re as _re2
                title_words = _re2.findall(r'\b[A-Za-z]{4,}\b', title)
                noise = {'support', 'request', 'feature', 'provide', 'need', 'customer',
                         'blocked', 'sale', 'seats', 'services', 'service', 'azure',
                         'microsoft', 'please', 'help', 'want', 'would', 'could',
                         'should', 'with', 'from', 'that', 'this', 'have', 'been'}
                meaningful = [w for w in title_words if w.lower() not in noise]
                if meaningful:
                    # Use first two meaningful words as keyword filter
                    search_term = meaningful[0]
                    print(f"[TFT Search] Using title keyword filter: CONTAINS '{search_term}'")
                    product_filter = f"AND [System.Title] CONTAINS '{search_term}'"
                else:
                    product_filter = ""
            else:
                # Step 2: Use the base service name directly - CONTAINS will match all variations
                # "Route Server" matches: "Route Server", "Azure Route Server", "Route Server - IPv6", etc.
                print(f"[TFT Search] Using service filter: CONTAINS '{base_service_name}'")
                product_filter = f"AND [System.Title] CONTAINS '{base_service_name}'"

            
            # WIQL query to find Features (exclude Closed state)
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
            
            print(f"[TFT Search] WIQL Query:\n{wiql_query}")
            
            wiql_url = f"{tft_base_url}/{quote(tft_project)}/_apis/wit/wiql?api-version={self.config.API_VERSION}&$top=200"
            wiql_response = requests.post(
                wiql_url,
                headers=tft_headers,
                json={'query': wiql_query}
            )
            
            if wiql_response.status_code != 200:
                try:
                    err_body = wiql_response.json()
                except Exception:
                    err_body = wiql_response.text[:500]
                print(f"[TFT Search] WIQL query failed: {wiql_response.status_code} — {err_body}")
                return []
            
            work_items = wiql_response.json().get('workItems', [])
            if not work_items:
                print("[TFT Search] No Features found in last 12 months")
                return []
            
            print(f"[TFT Search] Found {len(work_items)} Features, calculating similarity...")
            
            # Get detailed work item info (limit to 200 since we have product-filtered results)
            work_item_ids = [str(wi['id']) for wi in work_items[:200]]
            batch_url = f"{tft_base_url}/{quote(tft_project)}/_apis/wit/workitemsbatch?api-version={self.config.API_VERSION}"
            
            batch_response = requests.post(
                batch_url,
                headers=tft_headers,
                json={
                    'ids': work_item_ids,
                    'fields': ['System.Id', 'System.Title', 'System.Description', 'System.State', 'System.CreatedDate']
                }
            )
            
            if batch_response.status_code != 200:
                print(f"[TFT Search] Batch request failed: {batch_response.status_code}")
                return []
            
            # Parse all items first (shared by both AI and fallback paths)
            all_items = batch_response.json().get('value', [])
            print(f"[TFT Search] Processing {len(all_items)} product-filtered features...")
            
            # Limit to 100 items max
            if len(all_items) > 100:
                print(f"[TFT Search] Limiting from {len(all_items)} to 100 features")
                all_items = all_items[:100]
            
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
            
            # Try AI semantic search first, fall back to keyword matching
            print("[TFT Search] Using AI semantic search for similarity matching...")
            try:
                from embedding_service import EmbeddingService
                import time
                
                embedding_service = EmbeddingService()
                
                # Generate embedding for search query
                search_text = f"{title} {description}"
                search_embedding = embedding_service.embed(search_text)
                
                print(f"[TFT Search] Running AI embeddings on {len(parsed_items)} features")
                
                matches = []
                
                # Process in smaller batches to avoid rate limits
                batch_size = 10
                for i in range(0, len(parsed_items), batch_size):
                    batch_items = parsed_items[i:i+batch_size]
                    
                    for p_item in batch_items:
                        try:
                            feature_text = f"{p_item['title']} {p_item['description']}" if p_item['description'] else p_item['title']
                            feature_embedding = embedding_service.embed(feature_text)
                            
                            similarity = embedding_service.cosine_similarity(search_embedding, feature_embedding)
                            
                            if similarity >= threshold:
                                matches.append({
                                    **p_item,
                                    'similarity': round(similarity, 2),
                                })
                        except Exception as e:
                            if '429' in str(e) or 'RateLimitReached' in str(e):
                                print(f"[TFT Search] Rate limit hit, stopping AI search early")
                                raise
                            continue
                    
                    if i + batch_size < len(parsed_items):
                        time.sleep(0.5)
                
                matches.sort(key=lambda x: x['similarity'], reverse=True)
                
                print(f"[TFT Search] AI semantic search found {len(matches)} Features above threshold {threshold}")
                return matches[:10]
                
            except Exception as e:
                print(f"[TFT Search] AI semantic search failed: {e}")
                print(f"[TFT Search] Falling back to keyword matching for {len(parsed_items)} features...")
                
                # FALLBACK: Simple keyword matching
                # WIQL already filtered by service name, so these features are relevant.
                # Score by word overlap with the search query.
                import re as _re
                
                search_words = set(_re.findall(r'\b[a-z]{3,}\b', f"{title} {description}".lower()))
                stop_words = {'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was',
                              'will', 'has', 'have', 'been', 'not', 'but', 'they', 'their',
                              'them', 'which', 'when', 'what', 'where', 'who', 'how', 'all',
                              'can', 'would', 'could', 'should', 'into', 'also', 'than',
                              'customer', 'services', 'service', 'support', 'request', 'feature',
                              'new', 'need', 'sale', 'seats', 'blocked', 'related', 'requires'}
                search_words -= stop_words
                
                matches = []
                for p_item in parsed_items:
                    feature_words = set(_re.findall(r'\b[a-z]{3,}\b',
                                                     f"{p_item['title']} {p_item['description']}".lower()))
                    feature_words -= stop_words
                    
                    if not search_words or not feature_words:
                        overlap = 0.0
                    else:
                        common = search_words & feature_words
                        overlap = len(common) / min(len(search_words), len(feature_words))
                    
                    # Low threshold since WIQL already pre-filtered by service name
                    if overlap >= 0.15 or len(parsed_items) <= 10:
                        matches.append({
                            **p_item,
                            'similarity': round(min(overlap + 0.1, 0.99), 2),
                        })
                
                matches.sort(key=lambda x: x['similarity'], reverse=True)
                print(f"[TFT Search] Keyword fallback found {len(matches)} Features")
                return matches[:10]
            
        except Exception as e:
            print(f"[TFT Search] Error: {e}")
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
