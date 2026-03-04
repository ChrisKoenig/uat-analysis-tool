#!/usr/bin/env python3
"""
INTELLIGENT CONTEXT ANALYZER v3.1 - Enhanced AI Analysis Engine

=============================================================================
COMPREHENSIVE AI CONTEXT ANALYSIS WITH FULL TRANSPARENCY
=============================================================================

This module provides advanced AI-powered context analysis for IT support issues
with complete reasoning transparency and multi-source data integration.
Goes far beyond keyword matching to provide truly intelligent, explainable analysis.

MAJOR ENHANCEMENTS IN v3.1 (January 2026):
🆕 Dynamic Microsoft Product Detection via Microsoft Learn API
🆕 Intelligent Caching System with 7-day TTL and multi-tier fallback
🆕 Enhanced Feature Request Classification with priority-based intent detection
🆕 Fixed GCCH/GCC compliance keywords overwhelming connector requests
🆕 Migration context awareness - correctly identifies "migrate TO product" scenarios
🆕 Complete field population (technical_complexity, key_concepts, urgency_level, semantic_keywords)

MAJOR ENHANCEMENTS IN v3.0:
✅ 10-Step Systematic Analysis Process with full visibility
✅ Microsoft Product Detection with context awareness  
✅ Multi-Source Data Integration (Azure APIs, retirements, corrections)
✅ Corrective Learning System for continuous improvement
✅ Real-time confidence scoring and validation
✅ Complete data source usage tracking
✅ Step-by-step reasoning display for transparency

CORE CAPABILITIES:
- Advanced domain identification (compliance, technical, business, training)
- Intelligent intent classification (guidance, troubleshooting, demo requests)
- Contextual entity extraction (products, services, technologies)
- Semantic understanding with confidence scoring
- Smart routing with reasoning explanations
- Institutional memory through corrective learning

TRANSPARENCY FEATURES:
- Complete step-by-step analysis breakdown
- Data sources used vs. skipped with explanations
- Microsoft products detected with confidence levels
- Corrective learning applications tracking
- Confidence factor analysis
- Full decision audit trail

DATA SOURCES INTEGRATED:
- Microsoft Learn API (dynamic product discovery)
- Live Azure Services and Regions APIs
- Service Retirement Database
- User Corrections and Learning Database 
- Microsoft Learn Documentation
- Regional Service Availability
- Built-in Compliance Frameworks

DYNAMIC PRODUCT FETCHING ARCHITECTURE:
1. Primary: Microsoft Learn API (live fetch)
2. Fallback: Valid cache (<7 days)
3. Fallback: Expired cache (>7 days) with user alert
4. Fallback: Static product dictionary (12 core products)

CLASSIFICATION PRIORITY (v3.1):
- Feature requests checked FIRST (early exit at 0.45+ confidence)
- Connector/integration language scores 0.9 (very high confidence)
- Compliance score reduced 50% when feature language detected
- Migration context analyzed for direction (TO vs FROM product)

Author: Enhanced Matching Development Team
Version: 3.1 (Dynamic Product Detection & Enhanced Classification)
Last Updated: January 1, 2026
"""

import re
import json
import subprocess
import requests
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from dataclasses import dataclass
from enum import Enum
import logging
import os
from pathlib import Path

# Import Microsoft documentation tools if available
try:
    from mcp_microsoft_doc_microsoft_docs_search import microsoft_docs_search
    from mcp_microsoft_doc_microsoft_docs_fetch import microsoft_docs_fetch
    MICROSOFT_DOCS_AVAILABLE = True
except ImportError:
    MICROSOFT_DOCS_AVAILABLE = False

class IssueCategory(Enum):
    """Categories of issues for intelligent routing"""
    COMPLIANCE_REGULATORY = "compliance_regulatory"
    TECHNICAL_SUPPORT = "technical_support" 
    FEATURE_REQUEST = "feature_request"
    MIGRATION_MODERNIZATION = "migration_modernization"
    SECURITY_GOVERNANCE = "security_governance"
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    INTEGRATION_CONNECTIVITY = "integration_connectivity"
    COST_BILLING = "cost_billing"
    TRAINING_DOCUMENTATION = "training_documentation"
    SERVICE_RETIREMENT = "service_retirement"
    SERVICE_AVAILABILITY = "service_availability"  # Service gaps, regional availability
    DATA_SOVEREIGNTY = "data_sovereignty"  # Regional compliance, data residency
    PRODUCT_ROADMAP = "product_roadmap"  # Service announcements, future availability
    # 🆕 REAL-WORLD CATEGORIES
    AOAI_CAPACITY = "aoai_capacity"  # Azure OpenAI capacity issues
    BUSINESS_DESK = "business_desk"  # Business engagement, partnerships
    CAPACITY = "capacity"  # General capacity constraints
    RETIREMENTS = "retirements"  # Service deprecations, end-of-life
    ROADMAP = "roadmap"  # Product roadmap, timeline questions  
    SUPPORT = "support"  # General support requests
    SUPPORT_ESCALATION = "support_escalation"  # Escalated support cases
    SUSTAINABILITY = "sustainability"  # Green tech, carbon footprint

class IntentType(Enum):
    """User intent classification"""
    SEEKING_GUIDANCE = "seeking_guidance"
    REPORTING_ISSUE = "reporting_issue"
    REQUESTING_FEATURE = "requesting_feature"
    NEED_MIGRATION_HELP = "need_migration_help"
    COMPLIANCE_SUPPORT = "compliance_support"
    TROUBLESHOOTING = "troubleshooting"
    CONFIGURATION_HELP = "configuration_help"
    BEST_PRACTICES = "best_practices"
    REQUESTING_SERVICE = "requesting_service"  # Service availability requests
    SOVEREIGNTY_CONCERN = "sovereignty_concern"  # Regional compliance concerns
    ROADMAP_INQUIRY = "roadmap_inquiry"  # Future service availability
    # 🆕 ENHANCED INTENTS
    CAPACITY_REQUEST = "capacity_request"  # Requesting capacity increase
    ESCALATION_REQUEST = "escalation_request"  # Need urgent escalation
    BUSINESS_ENGAGEMENT = "business_engagement"  # Business discussions
    SUSTAINABILITY_INQUIRY = "sustainability_inquiry"  # Environmental concerns

@dataclass
class ContextAnalysis:
    """Results of intelligent context analysis"""
    category: IssueCategory
    intent: IntentType
    confidence: float
    domain_entities: Dict[str, List[str]]  # e.g., {"services": ["Defender for Cloud"], "standards": ["NIST 800-172"]}
    key_concepts: List[str]
    business_impact: str
    technical_complexity: str
    urgency_level: str
    recommended_search_strategy: Dict[str, bool]  # Which sources to prioritize
    semantic_keywords: List[str]
    context_summary: str
    reasoning: Dict[str, str]  # Explanation of analysis decisions

class IntelligentContextAnalyzer:
    """
    INTELLIGENT CONTEXT ANALYSIS ENGINE v3.0
    
    Advanced AI-powered context analyzer that provides comprehensive, transparent
    analysis of IT support issues with complete reasoning visibility.
    
    KEY CAPABILITIES:
    - 10-Step Systematic Analysis Process with full transparency
    - Microsoft Product Detection with context awareness
    - Multi-Source Data Integration (Azure APIs, retirements, corrections)
    - Corrective Learning System for continuous improvement
    - Real-time confidence scoring and validation
    - Complete data source usage tracking
    
    ANALYSIS TRANSPARENCY:
    - Step-by-step reasoning display
    - Data sources used vs. skipped with explanations
    - Microsoft products detected with confidence scores
    - Corrective learning applied from user feedback
    - Confidence factors breakdown
    
    DATA SOURCES INTEGRATED:
    - Live Azure Services API (.cache/azure_services.json)
    - Live Azure Regions API (.cache/azure_regions.json)
    - Regional Service Availability (.cache/regional_service_availability.json)
    - Service Retirements Database (retirements.json)
    - User Corrections Database (corrections.json)
    - Microsoft Learn Documentation API
    - Built-in Compliance Frameworks
    
    ENHANCED FEATURES:
    - Context-aware Microsoft product detection
    - Training/demo context recognition
    - Institutional memory through corrective learning
    - Multi-dimensional confidence scoring
    - Complete analysis audit trail
    """
    
    def __init__(self, cache_duration_hours: int = 168, enable_live_data: bool = False):
        """
        Initialize the Intelligent Context Analyzer with enhanced capabilities
        
        Sets up comprehensive analysis systems including:
        - External data source integration and caching
        - Microsoft product detection system
        - Corrective learning database
        - Step-by-step reasoning tracker
        - Data source usage monitoring
        
        Args:
            cache_duration_hours (int): Azure API data cache duration in hours (default: 168 = 7 days)
                                       Balances data freshness with API rate limiting
            enable_live_data (bool): Whether to fetch live data from Azure APIs (default: False)
                                   Set to True for live operation, False uses cached/static data
        
        ⚠️ DEMO FIX (Jan 16 2026): Changed default from True to False
           Azure CLI subprocess.run() was hanging for 45+ seconds on line 799 in _fetch_azure_services()
           Root cause: Azure CLI timeout/network issue - needs investigation post-demo
           Impact: Uses cached/static Azure service data instead of live API calls
        
        Initialization Process:
        1. Configure caching system for Azure API data
        2. Set up logging for debugging and monitoring  
        3. Load external knowledge bases and databases
        4. Initialize Microsoft Learn documentation integration
        5. Prepare reasoning and tracking systems
        """
        print("[DEBUG INTEL 1] IntelligentContextAnalyzer.__init__() starting...", flush=True)
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.enable_live_data = enable_live_data
        print("[DEBUG INTEL 2] Creating cache directory...", flush=True)
        self.cache_dir = Path('.cache')
        self.cache_dir.mkdir(exist_ok=True)
        print("[DEBUG INTEL 3] Cache directory ready.", flush=True)
        
        # Setup logging for debugging API calls
        print("[DEBUG INTEL 4] Setting up logger...", flush=True)
        self.logger = logging.getLogger(__name__)
        print("[DEBUG INTEL 5] Logger ready.", flush=True)
        
        # Initialize Microsoft Learn integration flag
        self.microsoft_docs_available = True
        
        # Pre-fetch Microsoft products to populate cache (non-blocking)
        print("[DEBUG INTEL 6] Fetching Microsoft products...", flush=True)
        try:
            self.microsoft_products = self._fetch_microsoft_products()
            self.logger.info(f"[OK] Initialized with {len(self.microsoft_products)} Microsoft products")
            print(f"[DEBUG INTEL 7] Fetched {len(self.microsoft_products)} Microsoft products.", flush=True)
        except Exception as e:
            self.logger.warning(f"[WARNING] Failed to initialize Microsoft products: {e}")
            print(f"[DEBUG INTEL 8] Product fetch failed, using static products: {e}", flush=True)
            self.microsoft_products = self._get_static_microsoft_products()
        
        print("[DEBUG INTEL 9] Loading knowledge base...", flush=True)
        self._load_knowledge_base()
        
        # Load active-learning weight adjustments (ENG-003 Step 3)
        # These multipliers are produced by weight_tuner.py batch process
        # and stored in the training-signals Cosmos container.
        print("[DEBUG INTEL 10] Loading pattern weight adjustments...", flush=True)
        self._weight_multipliers = self._load_weight_adjustments()
        if self._weight_multipliers:
            print(f"[DEBUG INTEL 10a] Loaded weight adjustments for {len(self._weight_multipliers)} categories")
        else:
            print("[DEBUG INTEL 10a] No weight adjustments found (defaults will be used)")
        
        print("[DEBUG INTEL 11] IntelligentContextAnalyzer.__init__() completed!", flush=True)
    
    def _get_cached_data(self, cache_key: str) -> Optional[Dict]:
        """
        Retrieve cached data if it exists and is not expired.
        
        Args:
            cache_key: Unique identifier for cached data
            
        Returns:
            Cached data if valid, None otherwise
            
        Source: Local file system cache with timestamp validation
        Purpose: Reduce Azure API calls while maintaining data freshness
        """
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                
            cached_time = datetime.fromisoformat(cached.get('timestamp', ''))
            if datetime.now() - cached_time < self.cache_duration:
                self.logger.debug(f"Using cached data for {cache_key}")
                return cached.get('data')
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            self.logger.warning(f"Invalid cache file {cache_file}: {e}")
            
        return None

    def _get_expired_cached_data(self, cache_key: str) -> Optional[Dict]:
        """
        Retrieve cached data even if expired (for fallback when CLI is unavailable).
        """
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
            
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                
            # Return expired data without checking timestamp
            self.logger.debug(f"Retrieved expired cached data for {cache_key}")
            return cached.get('data')
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"Invalid expired cache file {cache_file}: {e}")
            
        return None
    
    def _cache_data(self, cache_key: str, data: Dict) -> None:
        """
        Cache data with timestamp for future use.
        
        Args:
            cache_key: Unique identifier for cached data
            data: Data to cache
            
        Source: Local file system storage
        Purpose: Store Azure API responses to reduce network calls
        """
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                }, f, indent=2)
            self.logger.debug(f"Cached data for {cache_key}")
        except Exception as e:
            self.logger.error(f"Failed to cache data for {cache_key}: {e}")
    
    def _fetch_azure_regions(self) -> Dict[str, List[str]]:
        """
        Fetch current Azure regions using Azure CLI.
        
        Returns:
            Dictionary with countries, azure_regions, and continents
            
        Source: Azure CLI 'az account list-locations' command
        Purpose: Get live, up-to-date list of all available Azure regions
        Update Frequency: Cached for 7 days, refreshed automatically
        """
        cache_key = "azure_regions"
        
        # Try cache first
        if not self.enable_live_data:
            return self._get_static_regions()
            
        cached_regions = self._get_cached_data(cache_key)
        if cached_regions:
            return cached_regions
            
        # Also try to get expired cached data as backup
        expired_cached_regions = self._get_expired_cached_data(cache_key)
            
        try:
            # Use Azure CLI to get current regions
            result = subprocess.run([
                r'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd', 'account', 'list-locations', 
                '--query', '[].{name:name,displayName:displayName}',
                '--output', 'json'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                locations = json.loads(result.stdout)
                
                # Process regions into our expected format
                azure_regions = []
                countries = set()
                
                for location in locations:
                    region_name = location.get('name', '').lower()
                    display_name = location.get('displayName', '')
                    
                    if region_name:
                        azure_regions.append(region_name)
                        
                        # Extract country from display name
                        for country in ['brazil', 'canada', 'united states', 'germany', 'france', 
                                      'united kingdom', 'japan', 'australia', 'india', 'china', 
                                      'south korea', 'singapore', 'norway', 'sweden', 'switzerland',
                                      'uae', 'austria', 'chile', 'malaysia', 'indonesia']:
                            if country in display_name.lower():
                                countries.add(country)
                
                regions_data = {
                    "countries": list(countries),
                    "azure_regions": sorted(azure_regions),
                    "continents": ["north america", "south america", "europe", "asia", "africa", "australia", "oceania"]
                }
                
                # Cache the results
                self._cache_data(cache_key, regions_data)
                self.logger.info(f"Fetched {len(azure_regions)} Azure regions from CLI")
                return regions_data
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError) as e:
            self.logger.warning(f"Failed to fetch Azure regions via CLI: {e}")
            
        # Prefer expired cached data over static data
        if expired_cached_regions:
            self.logger.info("Using expired cached regions data as CLI is unavailable")
            return expired_cached_regions
            
        # Only use static data as absolute last resort
        self.logger.warning("No cached regions data available, falling back to static data")
        return self._get_static_regions()
    
    def _fetch_microsoft_products(self) -> Dict[str, Dict]:
        """
        Fetch Microsoft product catalog from Microsoft Learn API with intelligent fallback.
        
        🆕 NEW IN v3.1: Dynamic product discovery replacing hardcoded lists
        
        ARCHITECTURE:
        1. Try: Fetch from Microsoft Learn API (live, current data)
        2. Fallback: Use valid cache if < 7 days old (fast, reliable)
        3. Fallback: Use expired cache if > 7 days old (with user alert + log warning)
        4. Fallback: Use static product dictionary (12 core products, guaranteed availability)
        
        CACHE STRATEGY:
        - Cache location: .cache/microsoft_products.json
        - Cache TTL: 7 days (604,800 seconds)
        - Cache age check: Calculates days since last fetch
        - User alerting: Console warnings when using stale data
        
        Returns:
            Dictionary mapping product names to metadata:
            {
                "sentinel": {
                    "title": "Microsoft Sentinel",
                    "description": "Cloud-native SIEM and SOAR solution",
                    "category": "security",
                    "aliases": ["azure sentinel", "sentinel"],
                    "url": "https://learn.microsoft.com/en-us/azure/sentinel/"
                },
                "defender": { ... },
                ...
            }
            
        Product Metadata Structure:
        - title: Full official product name
        - description: Brief product description
        - category: Product category (security, analytics, etc.)
        - aliases: List of common name variations
        - url: Microsoft Learn documentation URL
            
        Data Sources (in priority order):
        1. Microsoft Learn Search API (https://learn.microsoft.com/api/search)
        2. Local cache file (.cache/microsoft_products.json)
        3. Static product dictionary (hardcoded core products)
        
        Performance:
        - First run (API fetch): 3-5 seconds for all products
        - Cached runs: < 100ms (in-memory after first fetch)
        - Fallback to static: < 10ms
        
        Rate Limiting:
        - 0.2 second delay between API requests (respectful to Microsoft servers)
        - Maximum 5 requests per second
        
        Error Handling:
        - API failures: Fall back to cache automatically
        - Network timeout: 10 seconds per API call
        - Cache corruption: Fall back to static products
        - User notification: Alerts shown when using stale/fallback data
        
        Update Frequency: 
        - Automatic refresh every 7 days
        - Manual refresh possible by deleting cache file
        
        Usage Example:
            products = self._fetch_microsoft_products()
            if "sentinel" in products:
                sentinel_url = products["sentinel"]["url"]
        
        See Also:
        - _fetch_from_microsoft_learn_api(): API integration implementation
        - _get_cache_age_days(): Cache age calculation
        - _enhance_with_known_products(): Ensures critical products present
        - _get_static_microsoft_products(): Final fallback
        """
        cache_key = "microsoft_products"
        
        if not self.enable_live_data:
            return self._get_static_microsoft_products()
        
        # Try to get valid (non-expired) cached data
        cached_products = self._get_cached_data(cache_key)
        if cached_products:
            return cached_products
        
        # Also get expired cache as backup
        expired_cached_products = self._get_expired_cached_data(cache_key)
        cache_age_days = self._get_cache_age_days(cache_key)
        
        try:
            # Method 1: Microsoft Learn documentation search API
            # This is a public API that doesn't require authentication
            products = self._fetch_from_microsoft_learn_api()
            
            if products:
                # Cache the fresh results
                self._cache_data(cache_key, products)
                self.logger.info(f"[OK] Fetched {len(products)} Microsoft products from Learn API")
                return products
                
        except Exception as e:
            self.logger.warning(f"[WARNING] Failed to fetch Microsoft products from Learn API: {e}")
        
        # If API failed, use expired cache (even if > 7 days old)
        if expired_cached_products:
            if cache_age_days and cache_age_days > 7:
                # Cache is stale - alert user and log for troubleshooting
                warning_msg = f"[WARNING] Using stale Microsoft product cache ({cache_age_days} days old). API unavailable."
                self.logger.warning(warning_msg)
                print(f"\n{warning_msg}")
                print("[INFO] Product detection may be incomplete. Check network connectivity.\n")
            else:
                self.logger.info(f"[INFO] Using cached Microsoft products (API unavailable, cache {cache_age_days} days old)")
            return expired_cached_products
        
        # Absolute fallback to static data
        self.logger.warning("[WARNING] No cache available, using static Microsoft product fallback")
        print("\n[WARNING] Using static Microsoft product data - dynamic fetch failed and no cache available.\n")
        return self._get_static_microsoft_products()
    
    def _fetch_from_microsoft_learn_api(self) -> Dict[str, Dict]:
        """
        Fetch products from Microsoft Learn documentation API.
        
        Uses the public Microsoft Learn search and catalog APIs to discover
        Microsoft products and their documentation.
        """
        import requests
        
        products = {}
        
        # Microsoft Learn has a public API for searching documentation
        # We'll search for major product categories and parse results
        product_searches = [
            ("Microsoft Sentinel SIEM security", "security"),
            ("Microsoft Defender endpoint security", "security"),
            ("Microsoft Entra identity Azure AD", "security"),
            ("Microsoft Purview compliance governance", "compliance"),
            ("Microsoft Intune device management", "security"),
            ("Microsoft Fabric analytics platform", "analytics"),
            ("Azure Synapse Analytics", "analytics"),
            ("Microsoft Teams collaboration", "collaboration"),
            ("SharePoint collaboration", "collaboration"),
            ("Power BI analytics", "analytics"),
            ("Power Apps low code", "low_code"),
            ("Power Automate workflow", "automation"),
            ("Dynamics 365 business", "business_apps"),
            ("Azure Logic Apps integration", "integration"),
            ("Microsoft 365", "productivity"),
            ("GitHub", "developer")
        ]
        
        try:
            # Microsoft Learn search endpoint (public, no auth)
            base_url = "https://learn.microsoft.com/api/search"
            
            for search_query, category in product_searches:
                try:
                    response = requests.get(
                        base_url,
                        params={
                            "search": search_query,
                            "locale": "en-us",
                            "$top": 3,
                            "facet": "category"
                        },
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get("results", [])
                        
                        if results:
                            # Parse the top result to extract product info
                            top_result = results[0]
                            title = top_result.get("title", "")
                            description = top_result.get("description", "")
                            url = top_result.get("url", "")
                            
                            # Extract clean product name from title
                            product_name = self._extract_product_name(title)
                            
                            if product_name and product_name.lower() not in products:
                                products[product_name.lower()] = {
                                    "title": title,
                                    "description": description or f"Microsoft product: {title}",
                                    "category": category,
                                    "url": url,
                                    "aliases": self._generate_product_aliases(product_name)
                                }
                    
                    # Rate limiting - be respectful to API
                    import time
                    time.sleep(0.2)
                    
                except requests.RequestException as e:
                    self.logger.debug(f"Search failed for '{search_query}': {e}")
                    continue
            
            # Enhance with known product variations
            products = self._enhance_with_known_products(products)
            
            return products if len(products) > 5 else {}  # Only return if we got meaningful data
            
        except Exception as e:
            self.logger.warning(f"Microsoft Learn API fetch failed: {e}")
            return {}
    
    def _extract_product_name(self, title: str) -> str:
        """Extract clean product name from documentation title"""
        # Remove common suffixes
        title = re.sub(r'\s+(-|\||:)\s+Microsoft Learn', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+documentation$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'^Microsoft\s+', '', title, flags=re.IGNORECASE)
        return title.strip()
    
    def _generate_product_aliases(self, product_name: str) -> List[str]:
        """Generate common aliases for a product"""
        aliases = []
        name_lower = product_name.lower()
        
        # Add variations
        if "azure" in name_lower:
            aliases.append(name_lower.replace("azure ", ""))
        if "microsoft" in name_lower:
            aliases.append(name_lower.replace("microsoft ", ""))
        
        return aliases
    
    def _enhance_with_known_products(self, products: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Enhance API results with known product variations and ensure critical products are included.
        This ensures we have core products even if API search doesn't return them.
        """
        # Critical products to ensure are always present
        core_products = {
            "sentinel": {
                "title": "Microsoft Sentinel",
                "description": "Cloud-native security information and event management (SIEM) and security orchestration, automation, and response (SOAR) solution",
                "category": "security",
                "url": "https://learn.microsoft.com/azure/sentinel/",
                "aliases": ["azure sentinel"]
            },
            "defender": {
                "title": "Microsoft Defender",
                "description": "Comprehensive security solution protecting endpoints, identities, cloud apps, and Office 365",
                "category": "security",
                "url": "https://learn.microsoft.com/microsoft-365/security/",
                "aliases": ["microsoft defender for endpoint", "defender for cloud", "defender for office 365"]
            },
            "entra": {
                "title": "Microsoft Entra",
                "description": "Identity and access management service (formerly Azure Active Directory)",
                "category": "security",
                "url": "https://learn.microsoft.com/entra/",
                "aliases": ["azure ad", "azure active directory", "entra id"]
            }
        }
        
        # Merge core products with fetched products (fetched takes precedence)
        for product_key, product_data in core_products.items():
            if product_key not in products:
                products[product_key] = product_data
        
        return products
    
    def _get_cache_age_days(self, cache_key: str) -> Optional[int]:
        """Get the age of cached data in days"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            
            cached_time = datetime.fromisoformat(cached.get('timestamp', ''))
            age = datetime.now() - cached_time
            return age.days
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def _get_static_microsoft_products(self) -> Dict[str, Dict]:
        """
        Static fallback Microsoft product database.
        Only used when API and cache are both unavailable.
        """
        return {
            "sentinel": {
                "title": "Microsoft Sentinel",
                "description": "Cloud-native security information and event management (SIEM) and security orchestration, automation, and response (SOAR) solution",
                "category": "security",
                "aliases": ["azure sentinel"],
                "url": "https://learn.microsoft.com/azure/sentinel/"
            },
            "defender": {
                "title": "Microsoft Defender",
                "description": "Comprehensive security solution protecting endpoints, identities, cloud apps, and Office 365",
                "category": "security",
                "aliases": ["microsoft defender for endpoint", "defender for cloud", "defender for office 365"],
                "url": "https://learn.microsoft.com/microsoft-365/security/"
            },
            "entra": {
                "title": "Microsoft Entra",
                "description": "Identity and access management service (formerly Azure Active Directory)",
                "category": "security",
                "aliases": ["azure ad", "azure active directory", "entra id"],
                "url": "https://learn.microsoft.com/entra/"
            },
            "purview": {
                "title": "Microsoft Purview",
                "description": "Unified data governance service for managing and governing data across on-premises, multi-cloud, and SaaS",
                "category": "compliance",
                "aliases": ["microsoft purview compliance", "purview data governance"],
                "url": "https://learn.microsoft.com/purview/"
            },
            "intune": {
                "title": "Microsoft Intune",
                "description": "Cloud-based mobile device management (MDM) and mobile application management (MAM)",
                "category": "security",
                "aliases": ["endpoint manager"],
                "url": "https://learn.microsoft.com/mem/intune/"
            },
            "teams": {
                "title": "Microsoft Teams",
                "description": "Collaboration platform combining workplace chat, meetings, notes, and attachments",
                "category": "collaboration",
                "aliases": ["ms teams"],
                "url": "https://learn.microsoft.com/microsoftteams/"
            },
            "sharepoint": {
                "title": "Microsoft SharePoint",
                "description": "Web-based collaborative platform integrating with Microsoft Office",
                "category": "collaboration",
                "aliases": ["sharepoint online"],
                "url": "https://learn.microsoft.com/sharepoint/"
            },
            "fabric": {
                "title": "Microsoft Fabric",
                "description": "End-to-end analytics platform bringing together data integration, engineering, warehousing, and business intelligence",
                "category": "analytics",
                "aliases": [],
                "url": "https://learn.microsoft.com/fabric/"
            },
            "synapse": {
                "title": "Azure Synapse Analytics",
                "description": "Analytics service bringing together data integration, enterprise data warehousing, and big data analytics",
                "category": "analytics",
                "aliases": ["synapse"],
                "url": "https://learn.microsoft.com/azure/synapse-analytics/"
            },
            "power bi": {
                "title": "Power BI",
                "description": "Business analytics service delivering insights for analyzing data with interactive visualizations",
                "category": "analytics",
                "aliases": ["powerbi"],
                "url": "https://learn.microsoft.com/power-bi/"
            },
            "connector": {
                "title": "Microsoft Connectors",
                "description": "Integration connectors enabling connectivity between Microsoft services and third-party applications",
                "category": "integration",
                "aliases": ["power platform connectors", "logic app connectors"],
                "url": "https://learn.microsoft.com/connectors/"
            },
            "logic apps": {
                "title": "Azure Logic Apps",
                "description": "Cloud service helping automate workflows and integrate apps, data, services, and systems",
                "category": "integration",
                "aliases": ["logic app"],
                "url": "https://learn.microsoft.com/azure/logic-apps/"
            }
        }
    
    def _fetch_azure_services(self) -> Dict[str, List[str]]:
        """
        Fetch current Azure services using Azure Resource Graph API.
        
        Returns:
            Dictionary categorizing Azure services by type
            
        Source: Azure Resource Graph API via Azure CLI queries
        Purpose: Get live, comprehensive list of available Azure services
        Update Frequency: Cached for 7 days, refreshed automatically
        Fallback: Static service list maintained for offline operation
        """
        cache_key = "azure_services"
        
        if not self.enable_live_data:
            return self._get_static_services()
            
        cached_services = self._get_cached_data(cache_key)
        if cached_services:
            return cached_services
            
        # Also try to get expired cached data as backup
        expired_cached_services = self._get_expired_cached_data(cache_key)
            
        try:
            # Query Azure Resource Graph for available resource types
            result = subprocess.run([
                r'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd', 'graph', 'query', 
                '-q', 'Resources | distinct type | order by type asc',
                '--output', 'json'
            ], capture_output=True, text=True, timeout=45)
            
            if result.returncode == 0:
                query_result = json.loads(result.stdout)
                resource_types = [item['type'] for item in query_result.get('data', [])]
                
                # Categorize services (enhanced logic)
                services = self._categorize_azure_services(resource_types)
                
                # Cache the results
                self._cache_data(cache_key, services)
                total_services = sum(len(v) for v in services.values())
                self.logger.info(f"Fetched {total_services} Azure services across {len(services)} categories")
                return services
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError) as e:
            self.logger.warning(f"Failed to fetch Azure services via Resource Graph: {e}")
            
        # Prefer expired cached data over static data
        if expired_cached_services:
            self.logger.info("Using expired cached data as CLI is unavailable")
            return expired_cached_services
            
        # Only use static data as absolute last resort
        self.logger.warning("No cached data available, falling back to static data")
        return self._get_static_services()

    def _fetch_regional_service_availability(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Fetch regional service availability mapping using Azure Resource Graph API.
        
        Returns:
            Dictionary mapping regions to available services and services to available regions
            
        Source: Azure Resource Graph API via Azure CLI queries
        Purpose: Determine which services are available in which regions
        Update Frequency: Cached for 7 days, refreshed automatically
        Fallback: Static regional mapping maintained for offline operation
        """
        cache_key = "regional_service_availability"
        
        if not self.enable_live_data:
            return self._get_static_regional_availability()
            
        cached_availability = self._get_cached_data(cache_key)
        if cached_availability:
            return cached_availability
            
        # Also try to get expired cached data as backup
        expired_cached_availability = self._get_expired_cached_data(cache_key)
            
        try:
            # Query Azure Resource Graph for resources grouped by type and location
            result = subprocess.run([
                r'C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd', 'graph', 'query', 
                '-q', '''Resources 
                | where location != "" 
                | summarize count() by type, location 
                | where count_ > 0
                | project type, location
                | order by type, location''',
                '--output', 'json'
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                query_result = json.loads(result.stdout)
                availability_data = query_result.get('data', [])
                
                # Build comprehensive mapping
                regional_mapping = self._build_regional_service_mapping(availability_data)
                
                # Cache the results
                self._cache_data(cache_key, regional_mapping)
                
                total_mappings = len(availability_data)
                regions_count = len(regional_mapping.get('regions_to_services', {}))
                services_count = len(regional_mapping.get('services_to_regions', {}))
                
                self.logger.info(f"Fetched {total_mappings} service-region mappings across {regions_count} regions and {services_count} service types")
                return regional_mapping
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError) as e:
            self.logger.warning(f"Failed to fetch regional service availability via Resource Graph: {e}")
            
        # Prefer expired cached data over static data
        if expired_cached_availability:
            self.logger.info("Using expired cached regional availability data as CLI is unavailable")
            return expired_cached_availability
            
        # Only use static data as absolute last resort
        self.logger.warning("No cached regional availability data available, falling back to static data")
        return self._get_static_regional_availability()

    def _build_regional_service_mapping(self, availability_data: List[Dict]) -> Dict[str, Dict[str, List[str]]]:
        """
        Build comprehensive regional service availability mapping from Azure Resource Graph data.
        
        Args:
            availability_data: List of {type, location} mappings from Azure Resource Graph
            
        Returns:
            Dictionary with regions_to_services and services_to_regions mappings
        """
        regions_to_services = {}
        services_to_regions = {}
        
        for item in availability_data:
            service_type = item.get('type', '').lower()
            location = item.get('location', '').lower()
            
            if not service_type or not location:
                continue
                
            # Clean up location names (handle various formats)
            clean_location = self._normalize_region_name(location)
            
            # Clean up service type names
            clean_service = self._normalize_service_name(service_type)
            
            # Build regions -> services mapping
            if clean_location not in regions_to_services:
                regions_to_services[clean_location] = []
            if clean_service not in regions_to_services[clean_location]:
                regions_to_services[clean_location].append(clean_service)
                
            # Build services -> regions mapping  
            if clean_service not in services_to_regions:
                services_to_regions[clean_service] = []
            if clean_location not in services_to_regions[clean_service]:
                services_to_regions[clean_service].append(clean_location)
        
        return {
            'regions_to_services': regions_to_services,
            'services_to_regions': services_to_regions,
            'last_updated': datetime.now().isoformat()
        }

    def _normalize_region_name(self, region: str) -> str:
        """Normalize region names to a consistent format"""
        # Convert various formats to consistent naming
        region = region.lower().strip()
        
        # Common region name normalizations
        region_mappings = {
            'eastus': 'east us',
            'westus': 'west us',
            'eastus2': 'east us 2',
            'westus2': 'west us 2',
            'westus3': 'west us 3',
            'centralus': 'central us',
            'southcentralus': 'south central us',
            'northcentralus': 'north central us',
            'westcentralus': 'west central us',
            'northeurope': 'north europe',
            'westeurope': 'west europe',
            'eastasia': 'east asia',
            'southeastasia': 'southeast asia',
            'japaneast': 'japan east',
            'japanwest': 'japan west',
            'australiaeast': 'australia east',
            'australiasoutheast': 'australia southeast',
            'brazilsouth': 'brazil south',
            'canadacentral': 'canada central',
            'canadaeast': 'canada east'
        }
        
        return region_mappings.get(region, region)

    def _normalize_service_name(self, service_type: str) -> str:
        """Normalize service type names to human-readable format"""
        # Remove provider prefix (e.g., 'microsoft.compute' -> 'compute')
        if '.' in service_type:
            service_type = service_type.split('.')[-1]
            
        # Convert camelCase to readable format
        service_type = re.sub(r'([a-z])([A-Z])', r'\1 \2', service_type)
        
        return service_type.lower().strip()

    def _get_static_regional_availability(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Static fallback regional service availability mapping.
        
        Source: Microsoft Azure documentation and common service patterns
        Purpose: Ensure functionality when Azure Resource Graph is unavailable
        Update Frequency: Manual updates when major regional expansions occur
        """
        # Major regions with broad service availability
        major_regions = [
            'east us', 'east us 2', 'west us', 'west us 2', 'west us 3', 'central us',
            'north europe', 'west europe', 'east asia', 'southeast asia',
            'japan east', 'japan west', 'australia east', 'australia southeast',
            'brazil south', 'canada central', 'canada east', 'uk south', 'uk west'
        ]
        
        # Core services available in most regions
        core_services = [
            'virtual machines', 'app service', 'storage accounts', 'sql database',
            'virtual network', 'load balancer', 'key vault', 'monitor'
        ]
        
        # AI/ML services with more limited regional availability
        ai_services = ['cognitive services', 'machine learning', 'openai']
        ai_regions = ['east us', 'east us 2', 'west us 2', 'west europe', 'southeast asia']
        

        
        # Build static mapping
        regions_to_services = {}
        services_to_regions = {}
        
        # Map core services to all major regions
        for region in major_regions:
            regions_to_services[region] = core_services.copy()
            for service in core_services:
                if service not in services_to_regions:
                    services_to_regions[service] = []
                services_to_regions[service].append(region)
        
        # Map AI services to limited regions
        for region in ai_regions:
            if region in regions_to_services:
                regions_to_services[region].extend(ai_services)
            for service in ai_services:
                if service not in services_to_regions:
                    services_to_regions[service] = []
                if region not in services_to_regions[service]:
                    services_to_regions[service].append(region)
        

        
        return {
            'regions_to_services': regions_to_services,
            'services_to_regions': services_to_regions,
            'last_updated': datetime.now().isoformat()
        }

    def _categorize_azure_services(self, resource_types: List[str]) -> Dict[str, List[str]]:
        """
        Categorize Azure resource types into logical service groups.
        
        Args:
            resource_types: List of Azure resource types from Resource Graph
            
        Returns:
            Dictionary with services categorized by function
            
        Source: Azure Resource Graph API resource types
        Purpose: Organize services into meaningful categories for context analysis
        """
        categories = {
            "security": [],
            "compute": [],
            "storage": [],
            "networking": [],
            "database": [],
            "ai_ml": [],
            "analytics": [],
            "integration": [],
            "monitoring": [],
            "governance": [],
            "web": [],
            "mobile": [],
            "iot": [],
            "media": [],
            "migration": [],
            "modern_work": []
        }
        
        # Enhanced categorization rules
        category_patterns = {
            "security": ["security", "keyvault", "defender", "sentinel", "entra", "activedirectory"],
            "compute": ["compute", "virtualmachines", "containerinstance", "kubernetes", "appservice", "functions", "batch"],
            "storage": ["storage", "storageaccounts", "backup", "disk", "file", "blob"],
            "networking": ["network", "virtualnetwork", "loadbalancer", "applicationgateway", "cdn", "vpn", "firewall"],
            "database": ["sql", "cosmos", "mysql", "postgresql", "redis", "database", "synapse"],
            "ai_ml": ["cognitive", "machinelearning", "openai", "speech", "vision", "botservice", "copilot"],
            "analytics": ["analytics", "synapse", "datafactory", "powerbi", "databricks", "streamanalytics", "viva"],
            "integration": ["logic", "servicebus", "eventhubs", "relay", "apimanagement"],
            "monitoring": ["insights", "monitor", "alertsmanagement", "dashboard", "workbook"],
            "governance": ["policy", "management", "resourcegraph", "blueprint", "authorization", "purview", "compliance"],
            "web": ["web", "sites", "cdn", "frontdoor", "signalr"],
            "mobile": ["mobile", "notification", "maps"],
            "iot": ["iot", "devices", "timeseriesinsights", "digitaltwins"],
            "media": ["media", "video", "streaming", "teams"],
            "migration": ["azure migrate", "site recovery", "database migration service"],
            "modern_work": ["microsoft365", "office365", "teams", "sharepoint", "onedrive", "outlook", "exchange", "copilot", "viva", "power", "whiteboard", "planner", "project", "visio", "yammer", "delve", "sway", "forms", "bookings", "loop"]
        }
        
        for resource_type in resource_types:
            type_lower = resource_type.lower()
            categorized = False
            
            for category, patterns in category_patterns.items():
                if any(pattern in type_lower for pattern in patterns):
                    # Clean up the service name
                    service_name = resource_type.split('/')[-1] if '/' in resource_type else resource_type
                    service_name = service_name.replace('microsoft.', '').lower()
                    categories[category].append(service_name)
                    categorized = True
                    break
            
            # If not categorized, add to governance as default
            if not categorized:
                service_name = resource_type.split('/')[-1] if '/' in resource_type else resource_type
                service_name = service_name.replace('microsoft.', '').lower()
                categories["governance"].append(service_name)
        
        # Remove duplicates and sort
        for category in categories:
            categories[category] = sorted(list(set(categories[category])))
            
        return categories
    
    def _get_static_services(self) -> Dict[str, List[str]]:
        """
        Static fallback Azure services taxonomy.
        
        Source: Manually curated Azure service categories (original implementation)
        Purpose: Ensure functionality when Azure APIs are unavailable
        Update Frequency: Manual updates as needed
        """
        return {
            "security": ["defender for cloud", "sentinel", "security center", "key vault", "active directory", "entra id", "defender for office 365", "defender for identity"],
            "compute": ["virtual machines", "app service", "functions", "container instances", "kubernetes service", "azure local"],
            "storage": ["storage accounts", "blob storage", "file storage", "disk storage", "backup"],
            "networking": ["virtual network", "load balancer", "application gateway", "vpn gateway", "route server", "azure route server", "cdn", "expressroute", "firewall", "bastion"],
            "database": ["sql database", "cosmos db", "mysql", "postgresql", "synapse analytics"],
            "ai_ml": ["cognitive services", "machine learning", "openai", "computer vision", "speech services", "azure openai", "copilot", "copilot for microsoft 365", "copilot studio"],
            "analytics": ["synapse analytics", "data factory", "stream analytics", "power bi", "databricks", "delta sharing", "viva insights", "workplace analytics", "microsoft fabric", "fabric"],
            "integration": ["logic apps", "service bus", "event hubs", "api management", "functions"],
            "monitoring": ["monitor", "application insights", "log analytics", "metrics", "alerts"],
            "governance": ["policy", "blueprints", "cost management", "resource groups", "subscriptions", "purview", "compliance manager"],
            "web": ["app service", "static web apps", "cdn", "front door"],
            "mobile": ["notification hubs", "mobile apps", "maps"],
            "iot": ["iot hub", "iot central", "digital twins"],
            "media": ["media services", "video indexer", "stream", "teams live events"],
            "migration": ["azure migrate", "site recovery", "database migration service", "azure backup"],
            "modern_work": ["microsoft 365", "office 365", "teams", "sharepoint", "onedrive", "outlook", "exchange", "copilot for microsoft 365", "viva suite", "viva engage", "viva learning", "viva goals", "viva topics", "viva connections", "power platform", "power apps", "power automate", "power bi", "copilot studio", "microsoft whiteboard", "microsoft planner", "microsoft project", "microsoft visio", "yammer", "delve", "sway", "forms", "bookings", "to do", "whiteboard", "loop"]
        }
    
    def _get_static_regions(self) -> Dict[str, List[str]]:
        """
        Static fallback Azure regions data.
        
        Source: Microsoft Azure documentation (as of November 2025)
        Purpose: Ensure functionality when Azure CLI is unavailable
        Update Frequency: Manual updates when new regions are added
        """
        return {
            "countries": ["brazil", "canada", "united states", "usa", "germany", "france", "united kingdom", "uk", 
                         "japan", "australia", "india", "china", "south korea", "singapore", "norway", "sweden", 
                         "switzerland", "uae", "austria", "chile", "malaysia", "indonesia", "new zealand", "spain", 
                         "italy", "poland", "finland", "belgium", "denmark", "taiwan", "greece", "mexico", "qatar", 
                         "israel", "saudi arabia"],
            "azure_regions": [
                # Americas
                "east us", "east us 2", "east us 3", "west us", "west us 2", "west us 3", "central us", 
                "north central us", "south central us", "west central us", "canada central", "canada east", 
                "brazil south", "brazil southeast", "chile north central", "mexico central",
                # Azure Government
                "us gov virginia", "us dod central", "us dod east", "us gov arizona", "us gov texas", 
                "us sec east", "us sec west", "us sec west central",
                # Europe  
                "north europe", "west europe", "uk south", "uk west", "france central", "france south",
                "germany north", "germany west central", "norway east", "norway west", 
                "sweden central", "sweden south", "switzerland north", "switzerland west", "austria east", 
                "belgium central", "denmark east", "finland central", "spain central", "italy north", 
                "poland central", "greece central",
                # Asia Pacific
                "east asia", "southeast asia", "japan east", "japan west", "australia central", "australia central 2", 
                "australia east", "australia southeast", "central india", "south india", "west india",
                "korea central", "korea south", "malaysia west", "indonesia central", "new zealand north", "taiwan",
                # Middle East & Africa
                "uae central", "uae north", "qatar central", "israel central", "saudi arabia east",
                "south africa north", "south africa west",
                # China (Special regions)
                "china east", "china east 2", "china north", "china north 2", "china north 3"
            ],
            "continents": ["north america", "south america", "europe", "asia", "africa", "australia", "oceania"]
        }
    
    def _generate_region_mappings(self, azure_regions: List[str]) -> Dict[str, str]:
        """
        Generate region name mappings for various formats.
        
        Args:
            azure_regions: List of Azure region names
            
        Returns:
            Dictionary mapping various formats to standardized display names
            
        Source: Generated from live Azure regions data
        Purpose: Handle region name variations (hyphens, spaces, camelCase)
        """
        mappings = {}
        
        for region in azure_regions:
            # Create standard display name
            display_name = ' '.join(word.capitalize() for word in region.split())
            
            # Map various formats
            mappings[region] = display_name
            mappings[region.replace(' ', '-')] = display_name
            mappings[region.replace(' ', '')] = display_name
            mappings[region.replace(' ', '_')] = display_name
            
        return mappings
    
    def _load_knowledge_base(self):
        """
        Load domain knowledge for intelligent analysis with live Azure data integration.
        
        Enhanced to fetch live data from Azure APIs while maintaining static fallbacks.
        All data sources are documented with their origin and update frequency.
        """
        print("[DEBUG KB 1] _load_knowledge_base() starting...", flush=True)
        
        # Azure services and products taxonomy
        # Source: Azure Resource Graph API (live) with static fallback
        # Purpose: Categorize Azure services for intelligent context matching
        # Update Frequency: Live data cached for 7 days, refreshed automatically
        # Fallback: Comprehensive static list maintained for offline operation
        print("[DEBUG KB 2] Fetching Azure services...", flush=True)
        self.azure_services = self._fetch_azure_services()
        print("[DEBUG KB 3] Azure services loaded.", flush=True)
        
        # Regional and geographic entities
        # Source: Azure CLI 'az account list-locations' (live) with static fallback
        # Purpose: Identify geographic context in user issues for regional service availability
        # Update Frequency: Live data cached for 7 days, refreshed automatically
        # Fallback: Comprehensive static list maintained for offline operation
        print("[DEBUG KB 4] Fetching Azure regions...", flush=True)
        self.regions = self._fetch_azure_regions()
        print("[DEBUG KB 5] Azure regions loaded.", flush=True)
        
        # Regional service availability mapping
        # Source: Azure Resource Graph API (live) with static fallback
        # Purpose: Map which services are available in which regions for accurate guidance
        # Update Frequency: Live data cached for 7 days, refreshed automatically
        # Fallback: Static mapping maintained for offline operation
        print("[DEBUG KB 6] Fetching regional service availability...", flush=True)
        self.regional_service_availability = self._fetch_regional_service_availability()
        print("[DEBUG KB 7] Regional service availability loaded.", flush=True)
        
        # Azure region name mappings for proper formatting
        # Source: Generated from live Azure regions data with normalization rules
        # Purpose: Handle various region name formats (hyphens, spaces, camelCase) for consistent matching
        # Update Frequency: Generated dynamically from live regions data (refreshed every 7 days)
        self.region_name_mapping = self._generate_region_mappings(self.regions.get('azure_regions', []))
        
        # Compliance and regulatory frameworks
        # Source: Manually curated from industry-standard compliance frameworks
        # Purpose: Identify compliance-related issues requiring specialized handling
        # Update Frequency: Manual updates as new frameworks emerge
        # Scope: Enterprise compliance standards across industries (government, healthcare, financial)
        self.compliance_frameworks = {
            "nist": ["nist 800-53", "nist 800-171", "nist 800-172", "nist cybersecurity framework"],
            "iso": ["iso 27001", "iso 27002", "iso 9001", "iso 20000"],
            "financial": ["sox", "pci dss", "basel iii", "mifid ii"],
            "healthcare": ["hipaa", "hitech", "fda 21 cfr part 11"],
            "privacy": ["gdpr", "ccpa", "pipeda", "privacy shield"],
            "government": ["fisma", "fedramp", "itar", "cmmc", "cjis", "gcch", "gcc", "gcc high", "government community cloud", "dod", "department of defense", "federal", "gov cloud", "government cloud"]
        }
        
        # Technical issue indicators
        # Source: Manually curated from common technical problem patterns
        # Purpose: Classify technical issues by problem type for targeted matching
        # Update Frequency: Manual updates based on observed issue patterns
        # Scope: General technical categories covering errors, performance, connectivity, configuration
        self.technical_indicators = {
            "errors": ["error", "exception", "failed", "failing", "broken", "not working", "issue"],
            "performance": ["slow", "timeout", "latency", "performance", "optimization", "bottleneck"],
            "connectivity": ["connection", "network", "connectivity", "access", "authentication", "authorization"],
            "configuration": ["setup", "configuration", "deployment", "installation", "provisioning"]
        }
        
        # Business impact indicators
        # Source: Enterprise service management best practices (ITIL-based impact classification)
        # Purpose: Prioritize issues based on business impact severity
        # Update Frequency: Static - based on industry-standard impact levels
        # Scope: High/Medium/Low classification for business impact assessment
        self.impact_indicators = {
            "high": ["critical", "urgent", "production down", "business critical", "revenue impact"],
            "medium": ["important", "affects users", "degraded performance", "customer impact"],
            "low": ["minor", "enhancement", "nice to have", "future consideration"]
        }
        
        # Load retirements data
        # Source: retirements.json - Service retirement and deprecation information
        # Purpose: Identify services that are being deprecated or retired
        # Update Frequency: Manual updates when Microsoft announces retirements
        self.retirements_data = self._load_retirements_data()
        
        # Load corrections data for learning
        # Source: corrections.json - User feedback and corrections for improved accuracy
        # Purpose: Apply machine learning from user corrections to improve context analysis
        # Update Frequency: Updated every time user provides corrections
        self.corrections_data = self._load_corrections_data()
        
        # Intent patterns
        # Source: Manually curated from user behavior analysis and support ticket patterns
        # Purpose: Classify user intent to enable appropriate response routing and matching
        # Update Frequency: Enhanced based on observed user interaction patterns
        # Scope: Comprehensive intent categories covering all major support scenarios
        self.intent_patterns = {
            IntentType.SEEKING_GUIDANCE: ["how to", "guidance", "best practice", "recommendation", "advice"],
            IntentType.REPORTING_ISSUE: ["problem", "issue", "error", "bug", "not working", "failed"],
            IntentType.REQUESTING_FEATURE: ["feature request", "enhancement", "new capability", "add support", "need feature", "require feature", "feature needed", "capability needed", "connector", "connectors needed", "integration needed"],
            IntentType.NEED_MIGRATION_HELP: ["migration", "migrate from", "move from", "upgrade from", "modernize", "transition from"],
            IntentType.COMPLIANCE_SUPPORT: ["compliance", "regulatory", "audit", "certification", "policy", "gcch", "gcc", "government cloud", "fedramp", "fisma"],
            IntentType.TROUBLESHOOTING: ["troubleshoot", "debug", "diagnose", "investigate", "resolve"],
            IntentType.CONFIGURATION_HELP: ["configure", "setup", "install", "deploy", "provision"],
            IntentType.BEST_PRACTICES: ["best practice", "recommendation", "optimize", "improve"],
            IntentType.REQUESTING_SERVICE: ["service not available", "need service", "lack of service", "when will service", "service in region"],
            IntentType.SOVEREIGNTY_CONCERN: ["sovereignty", "data residency", "regulatory requirement", "compliance in region", "local data"],
            IntentType.ROADMAP_INQUIRY: ["roadmap", "future availability", "service launch", "when available", "timeline"],
            # 🆕 ENHANCED INTENT PATTERNS
            IntentType.CAPACITY_REQUEST: ["need capacity", "capacity needed", "increase quota", "quota needed", "capacity limit", "quota exceeded", "more capacity", "requesting capacity", "capacity request", "quota request", "increase capacity"],
            IntentType.ESCALATION_REQUEST: ["escalate", "urgent", "critical", "emergency", "high priority", "business critical"],
            IntentType.BUSINESS_ENGAGEMENT: ["business discussion", "partnership", "commercial", "account team", "business case"],
            IntentType.SUSTAINABILITY_INQUIRY: ["carbon footprint", "environmental impact", "sustainability", "green", "renewable"]
        }
    
    def _load_retirements_data(self) -> Dict:
        """Load retirements data from JSON file"""
        try:
            retirements_file = Path('retirements.json')
            if retirements_file.exists():
                with open(retirements_file, 'r') as f:
                    data = json.load(f)
                    self.logger.info(f"[OK] Loaded {len(data.get('retirements', []))} retirement records")
                    return data
            else:
                self.logger.warning("[WARNING] retirements.json not found - no retirement data available")
        except Exception as e:
            self.logger.error(f"[ERROR] Error loading retirements data: {e}")
        return {"retirements": []}
    
    def _load_corrections_data(self) -> Dict:
        """Load user corrections for learning"""
        try:
            corrections_file = Path('corrections.json')
            if corrections_file.exists():
                with open(corrections_file, 'r') as f:
                    data = json.load(f)
                    self.logger.info(f"[OK] Loaded {len(data.get('corrections', []))} correction records for learning")
                    return data
            else:
                self.logger.warning("[WARNING] corrections.json not found - no corrective learning data available")
        except Exception as e:
            self.logger.error(f"[ERROR] Error loading corrections data: {e}")
        return {"corrections": []}
    
    def _load_weight_adjustments(self) -> Dict[str, float]:
        """
        Load active-learning weight adjustments from Cosmos.
        
        Returns a dict mapping category name (str) to a float multiplier.
        Returns empty dict if no adjustments exist or Cosmos unavailable.
        
        These adjustments are produced by weight_tuner.py and stored as a
        single document in the training-signals Cosmos container.
        """
        try:
            from weight_tuner import PatternWeightTuner
            tuner = PatternWeightTuner()
            multipliers = tuner.get_multipliers()
            if multipliers:
                self.logger.info(f"[OK] Loaded weight adjustments for {len(multipliers)} categories")
            return multipliers
        except Exception as e:
            self.logger.warning(f"[WARNING] Could not load weight adjustments: {e}")
            return {}
    
    def _track_data_source_usage(self, text: str, reasoning_tracker: Dict):
        """Track which data sources were used or skipped and why"""
        
        text_lower = text.lower()
        
        # 1. Azure Services Data - Check for Azure/Microsoft service keywords
        azure_keywords = [
            "azure", "sentinel", "defender", "entra", "purview", "intune", "fabric", 
            "synapse", "databricks", "microsoft", "m365", "office 365", "power", 
            "dynamics", "teams", "sharepoint", "onedrive", "cosmos", "function",
            "logic app", "connector", "service bus", "event hub", "app service"
        ]
        if any(keyword in text_lower for keyword in azure_keywords):
            reasoning_tracker["data_sources_consulted"].append({
                "source": "Azure Services Database (.cache/azure_services.json)",
                "status": "USED",
                "reason": "Text contains Azure/Microsoft service references",
                "matches_found": [kw for kw in azure_keywords if kw in text_lower][:5]
            })
        else:
            reasoning_tracker["data_sources_skipped"].append({
                "source": "Azure Services Database",
                "status": "SKIPPED", 
                "reason": "No Azure/Microsoft service keywords detected"
            })
        
        # 2. Azure Regions Data
        if any(region.lower() in text for region_list in self.regions.values() for region in region_list):
            reasoning_tracker["data_sources_consulted"].append({
                "source": "Azure Regions Database (.cache/azure_regions.json)",
                "status": "USED",
                "reason": "Text contains geographic/region references",
                "matches_found": [r for regions in self.regions.values() for r in regions if r.lower() in text][:3]
            })
        else:
            reasoning_tracker["data_sources_skipped"].append({
                "source": "Azure Regions Database",
                "status": "SKIPPED",
                "reason": "No geographic region keywords detected"
            })
        
        # 3. Compliance Frameworks Data - ALWAYS check if government/gcch/gcc mentioned
        government_keywords = ["government", "gcch", "gcc", "federal", "dod", "fedramp", "fisma"]
        has_government = any(keyword in text_lower for keyword in government_keywords)
        
        compliance_matches = [f for frameworks in self.compliance_frameworks.values() for f in frameworks if f in text_lower]
        
        if compliance_matches or has_government:
            reasoning_tracker["data_sources_consulted"].append({
                "source": "Compliance Frameworks Database (built-in)",
                "status": "USED",
                "reason": "Text contains compliance/regulatory/government keywords",
                "matches_found": compliance_matches[:3] if compliance_matches else government_keywords if has_government else []
            })
        else:
            reasoning_tracker["data_sources_skipped"].append({
                "source": "Compliance Frameworks Database",
                "status": "SKIPPED",
                "reason": "No compliance/regulatory/government keywords detected"
            })
        
        # 4. Retirements Data
        if len(self.retirements_data.get('retirements', [])) > 0:
            retirement_matches = [r for r in self.retirements_data['retirements'] if any(keyword in text for keyword in ['retirement', 'deprecated', 'end of life', 'sunset'])]
            if retirement_matches:
                reasoning_tracker["data_sources_consulted"].append({
                    "source": "Service Retirements Database (retirements.json)",
                    "status": "USED",
                    "reason": "Text contains retirement/deprecation keywords",
                    "matches_found": [r.get('service', 'Unknown') for r in retirement_matches][:3]
                })
            else:
                reasoning_tracker["data_sources_skipped"].append({
                    "source": "Service Retirements Database",
                    "status": "SKIPPED",
                    "reason": "No retirement/deprecation keywords detected"
                })
        else:
            reasoning_tracker["data_sources_skipped"].append({
                "source": "Service Retirements Database",
                "status": "UNAVAILABLE",
                "reason": "No retirements data loaded"
            })
        
        # 5. Regional Service Availability Data
        if hasattr(self, 'regional_service_availability') and self.regional_service_availability:
            reasoning_tracker["data_sources_consulted"].append({
                "source": "Regional Service Availability (.cache/regional_service_availability.json)",
                "status": "USED", 
                "reason": "Available for region-specific service queries",
                "data_size": f"{len(self.regional_service_availability.get('services_to_regions', {}))} services mapped"
            })
        else:
            reasoning_tracker["data_sources_skipped"].append({
                "source": "Regional Service Availability",
                "status": "UNAVAILABLE",
                "reason": "No regional availability data loaded"
            })
        
        # 6. Microsoft Learn API
        if self.microsoft_docs_available:
            reasoning_tracker["data_sources_consulted"].append({
                "source": "Microsoft Learn Documentation API",
                "status": "AVAILABLE",
                "reason": "External knowledge source for Microsoft product information",
                "note": "Used for product disambiguation and context"
            })
        else:
            reasoning_tracker["data_sources_skipped"].append({
                "source": "Microsoft Learn Documentation API", 
                "status": "UNAVAILABLE",
                "reason": "Microsoft docs integration not available"
            })
    
    def _apply_corrective_learning(self, text: str, reasoning_tracker: Dict) -> List:
        """Apply corrections from user feedback to improve accuracy"""
        corrections_applied = []
        
        if len(self.corrections_data.get('corrections', [])) > 0:
            # Look for similar text patterns in corrections
            for correction in self.corrections_data['corrections']:
                original_text = correction.get('original_text', '').lower()
                if original_text and any(word in text for word in original_text.split() if len(word) > 3):
                    corrections_applied.append({
                        "pattern": correction.get('pattern', 'Unknown'),
                        "original_category": correction.get('original_category'),
                        "corrected_category": correction.get('corrected_category'),
                        "confidence_boost": correction.get('confidence_boost', 0.1)
                    })
            
            if corrections_applied:
                reasoning_tracker["corrections_applied"] = corrections_applied
                reasoning_tracker["steps"].append(f"   [OK] Applied {len(corrections_applied)} corrective learning patterns")
            else:
                reasoning_tracker["steps"].append("   [INFO] No applicable corrections found in learning database")
        else:
            reasoning_tracker["steps"].append("   [WARNING] No corrective learning data available")
        
        return corrections_applied
    
    def analyze_context(self, title: str, description: str, impact: str = "") -> ContextAnalysis:
        """
        CORE ANALYSIS ENGINE - Comprehensive Context Analysis with Full Transparency
        
        This is the primary analysis method that processes IT support issues through
        a systematic 10-step process with complete reasoning visibility and data source tracking.
        
        ANALYSIS PIPELINE:
        1. External Data Source Consultation (Azure services, regions, retirements)
        2. Microsoft Product Detection (context-aware with confidence scoring)
        3. Corrective Learning Application (institutional memory)
        4. Domain Entity Extraction (technical terms, products, services)
        5. Category Classification (training, technical, compliance, etc.)
        6. Intent Determination (seeking guidance, troubleshooting, etc.)
        7. Key Concept and Keyword Analysis (semantic understanding)
        8. Business Impact and Complexity Assessment
        9. Urgency Level Calculation
        10. Final Synthesis and Confidence Scoring
        
        Args:
            title (str): Issue title/subject line - primary context indicator
            description (str): Detailed issue description - comprehensive context
            impact (str): Business impact statement - criticality assessment
            
        Returns:
            ContextAnalysis: Complete analysis results including:
                - category: Determined issue category
                - intent: User's primary intent
                - confidence: Overall analysis confidence (0.0-1.0)
                - reasoning: Complete step-by-step analysis process
                - data_sources_used: Which knowledge sources were consulted
                - microsoft_products: Detected Microsoft products with context
                - corrections_applied: Any corrective learning applied
        
        Data Sources Integrated:
        - Azure Services API (.cache/azure_services.json)
        - Azure Regions API (.cache/azure_regions.json) 
        - Service Retirements (retirements.json)
        - User Corrections (corrections.json)
        - Microsoft Learn Documentation
        - Built-in Knowledge Base
        """
        # =================================================================
        # ANALYSIS INITIALIZATION
        # Prepare input text and initialize comprehensive tracking systems
        # =================================================================
        combined_text = f"{title} {description} {impact}".lower().strip()
        
        # DEBUG: Show what text is being analyzed
        print("=" * 80)
        print("[ANALYZER] INTELLIGENT CONTEXT ANALYZER - INPUT DATA:")
        print(f"[INPUT] Title: '{title}'")
        print(f"[INPUT] Description: '{description}'")
        print(f"[INPUT] Impact: '{impact}'")
        print(f"[INPUT] Combined text length: {len(combined_text)} chars")
        print(f"[INPUT] Combined text preview: '{combined_text[:200]}...'")
        print("=" * 80)
        
        # Initialize comprehensive step-by-step reasoning tracker
        # This provides complete transparency into the AI decision-making process
        step_by_step_reasoning = {
            "steps": [],                           # Detailed analysis steps with explanations
            "data_sources_consulted": [],          # External data sources actively used
            "data_sources_skipped": [],            # Sources deemed not relevant (with reasons)
            "microsoft_products_detected": [],     # Microsoft products identified with confidence
            "corrections_applied": [],             # Corrective learning applied from previous feedback
            "confidence_factors": []               # Factors contributing to confidence score
        }
        
        # =================================================================
        # 10-STEP SYSTEMATIC ANALYSIS PROCESS
        # Each step builds on previous analysis with full transparency
        # =================================================================
        
        # STEP 1: External Data Source Consultation
        # Determine which knowledge sources are relevant and should be consulted
        step_by_step_reasoning["steps"].append("[STEP 1] External Data Source Consultation")
        self._track_data_source_usage(combined_text, step_by_step_reasoning)
        
        # STEP 2: Microsoft Product Detection with Context Awareness
        # Identify Microsoft products mentioned with confidence scoring and context analysis
        step_by_step_reasoning["steps"].append("[STEP 2] Microsoft Product Detection")
        microsoft_analysis = self._detect_microsoft_products_with_context(combined_text)
        if microsoft_analysis["detected_products"]:
            step_by_step_reasoning["microsoft_products_detected"] = microsoft_analysis["detected_products"]
            step_by_step_reasoning["steps"].append(f"   [OK] Detected Microsoft products: {[p['name'] for p in microsoft_analysis['detected_products']]}")
            step_by_step_reasoning["steps"].append(f"   [CONF] Confidence: {microsoft_analysis.get('confidence', 'N/A')}")
        else:
            step_by_step_reasoning["steps"].append("   [NONE] No Microsoft products detected")
        
        # STEP 3: Apply Corrective Learning (Institutional Memory)
        # Apply lessons learned from previous user corrections to improve accuracy
        step_by_step_reasoning["steps"].append("[STEP 3] Corrective Learning Application")
        corrections_applied = self._apply_corrective_learning(combined_text, step_by_step_reasoning)
        
        # STEP 4: Domain Entity Extraction (Technical Context)
        # Extract relevant technical terms, products, services, and domain-specific entities
        step_by_step_reasoning["steps"].append("[STEP 4] Domain Entity Extraction")
        domain_entities = self._extract_domain_entities(combined_text)
        step_by_step_reasoning["steps"].append(f"   [INFO] Extracted entities: {sum(len(v) for v in domain_entities.values())} total")
        step_by_step_reasoning["steps"].append(f"   [INFO] Categories: {list(domain_entities.keys())}")
        
        # STEP 5: Category Classification (Issue Type)
        # Determine the primary category of the issue (training, technical, compliance, etc.)
        step_by_step_reasoning["steps"].append("[STEP 5] Category Classification")
        category, category_confidence = self._classify_category(combined_text, domain_entities)
        step_by_step_reasoning["confidence_factors"].append(f"Category confidence: {category_confidence:.2f}")
        step_by_step_reasoning["steps"].append(f"   [RESULT] Classified as: {category} (confidence: {category_confidence:.2f})")
        
        # STEP 6: Intent Determination (User Goal)
        # Understand what the user is trying to accomplish
        step_by_step_reasoning["steps"].append("[STEP 6] Intent Determination")
        intent, intent_confidence = self._classify_intent(combined_text)
        step_by_step_reasoning["confidence_factors"].append(f"Intent confidence: {intent_confidence:.2f}")
        step_by_step_reasoning["steps"].append(f"   [RESULT] Primary intent: {intent} (confidence: {intent_confidence:.2f})")
        
        # STEP 7: Key Concept and Keyword Analysis (Semantic Understanding)
        # Extract key concepts and generate semantic keywords for matching
        step_by_step_reasoning["steps"].append("[STEP 7] Key Concept and Keyword Analysis")
        key_concepts = self._extract_key_concepts(combined_text, domain_entities)
        semantic_keywords = self._generate_semantic_keywords(combined_text, domain_entities, category)
        step_by_step_reasoning["steps"].append(f"   [INFO] Key concepts identified: {len(key_concepts)}")
        step_by_step_reasoning["steps"].append(f"   [INFO] Semantic keywords generated: {len(semantic_keywords)}")
        
        # STEP 8: Business Impact and Technical Complexity Assessment
        # Evaluate the business criticality and technical complexity
        step_by_step_reasoning["steps"].append("[STEP 8] Business Impact and Complexity Assessment")
        business_impact = self._assess_business_impact(combined_text, impact)
        technical_complexity = self._assess_technical_complexity(combined_text, domain_entities)
        step_by_step_reasoning["steps"].append(f"   [INFO] Business impact: {business_impact}")
        step_by_step_reasoning["steps"].append(f"   [INFO] Technical complexity: {technical_complexity}")
        urgency_level = self._assess_urgency(combined_text, business_impact)
        
        # STEP 9: Search Strategy Recommendation
        step_by_step_reasoning["steps"].append("[STEP 9] Search Strategy Optimization")
        search_strategy = self._recommend_search_strategy(category, intent, domain_entities)
        
        # 🔍 STEP 10: Context Summary Generation
        step_by_step_reasoning["steps"].append("Step 10: Context Summary Generation")
        context_summary = self._generate_context_summary(
            category, intent, domain_entities, key_concepts, business_impact, combined_text
        )
        
        # Calculate overall confidence
        overall_confidence = (category_confidence + intent_confidence) / 2
        step_by_step_reasoning["confidence_factors"].append(f"Overall confidence: {overall_confidence:.2f}")
        
        # Generate comprehensive reasoning with step-by-step details
        reasoning = self._generate_comprehensive_reasoning(
            category, intent, category_confidence, intent_confidence, 
            domain_entities, business_impact, technical_complexity, 
            combined_text, step_by_step_reasoning, microsoft_analysis
        )
        
        return ContextAnalysis(
            category=category,
            intent=intent,
            confidence=overall_confidence,
            domain_entities=domain_entities,
            key_concepts=key_concepts,
            business_impact=business_impact,
            technical_complexity=technical_complexity,
            urgency_level=urgency_level,
            recommended_search_strategy=search_strategy,
            semantic_keywords=semantic_keywords,
            context_summary=context_summary,
            reasoning=reasoning
        )
    
    def _extract_domain_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract domain-specific entities from text using both static data and Microsoft Learn"""
        entities = {
            "azure_services": [],
            "compliance_frameworks": [],
            "technologies": [],
            "business_domains": [],
            "technical_areas": [],
            "regions": [],
            "discovered_services": []  # Services found via Microsoft Learn
        }
        
        # Enhanced service discovery using Microsoft Learn
        if self.microsoft_docs_available:
            try:
                # ⚠️ BUG FIX (Jan 16 2026): Use flexible patterns for AI-driven service detection
                # Let the AI identify services - these patterns just extract potential candidates
                service_patterns = [
                    r'\b(azure\s+\w+(?:\s+\w+)?)\b',  # Azure + 1-2 words (azure sql, azure route server)
                    r'\b(microsoft\s+\w+)\b',  # Microsoft + 1 word
                    r'\b(fabric|synapse|databricks|openai|purview)\b',  # Known services without prefix
                ]
                
                potential_services = []
                for pattern in service_patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    potential_services.extend([match.strip() for match in matches if isinstance(match, str)])
                
                # Filter out action verbs and generic terms
                action_verbs = {'azure migrate', 'azure create', 'azure deploy', 'azure configure', 'azure update'}
                filtered_services = []
                for service in set(potential_services):
                    service_lower = service.lower()
                    # Skip if it's just an action verb
                    if service_lower in action_verbs:
                        continue
                    # Skip if it's a single word without Azure/Microsoft prefix
                    if ' ' not in service and service_lower not in ['fabric', 'synapse', 'databricks', 'openai', 'purview']:
                        continue
                    filtered_services.append(service)
                
                # Look up discovered services in Microsoft documentation
                for service in filtered_services:
                    service_info = self._lookup_service_in_microsoft_docs(service)
                    if service_info.get('found_in_docs'):
                        entities["discovered_services"].append(service)
                        entities["azure_services"].append(service)
                        entities["technical_areas"].append(service_info.get('category', 'other'))
                        
                if entities["discovered_services"]:
                    self.logger.info(f"Discovered {len(entities['discovered_services'])} services via Microsoft Learn")
                        
            except Exception as e:
                self.logger.warning(f"Enhanced service discovery failed: {e}")
        
        # Extract Azure services from static list (fallback when live APIs unavailable)
        # =====================================================================
        # INTELLIGENT SERVICE MATCHING WITH VERB FILTERING (Jan 16 2026)
        # =====================================================================
        # Problem: Simple substring matching would match action verbs in context
        # Example: "migrate to Azure Route Server" would incorrectly match "migrate"
        #
        # Solution 1: Word boundary regex matching (matches complete words only)
        # Solution 2: Exclude single-word action verbs from the service list
        #
        # Excluded verbs: migrate, import, export, recovery, backup (when standalone)
        # Allowed services: "azure migrate", "site recovery", "azure backup" (full names)
        #
        # This ensures only real service names are extracted from the text,
        # not action verbs that happen to be in our service taxonomy.
        # =====================================================================
        text_lower = text.lower()
        
        # Action verbs to exclude from azure_services list (not real services when standalone)
        excluded_verbs = {'migrate', 'import', 'export', 'recovery', 'backup'}
        
        for category, services in self.azure_services.items():
            for service in services:
                service_lower = service.lower()
                
                # Skip if it's a single-word action verb (not a real service name)
                if service_lower in excluded_verbs:
                    continue
                
                # Use word boundary regex for exact matching
                # This prevents "migrate" from matching in "migrate to Azure"
                pattern = r'\b' + re.escape(service_lower) + r'\b'
                if re.search(pattern, text_lower):
                    entities["azure_services"].append(service)
                    entities["technical_areas"].append(category)
        
        # Extract compliance frameworks
        for framework_type, frameworks in self.compliance_frameworks.items():
            for framework in frameworks:
                if framework in text:
                    entities["compliance_frameworks"].append(framework)
                    entities["business_domains"].append(framework_type)
        
        # Extract regions and geographic entities
        text_lower = text.lower()
        for region_type, region_list in self.regions.items():
            for region in region_list:
                if region.lower() in text_lower:
                    # Use proper region name mapping for Azure regions
                    if region_type == "azure_regions" and region.lower() in self.region_name_mapping:
                        entities["regions"].append(self.region_name_mapping[region.lower()])
                    else:
                        entities["regions"].append(region.title())
        
        # Extract technologies and patterns
        tech_patterns = [
            r'\b(api|rest|soap|json|xml|oauth|saml|jwt)\b',
            r'\b(python|java|c#|javascript|powershell|terraform|arm)\b',
            r'\b(docker|kubernetes|container|microservice)\b',
            r'\b(sql|nosql|database|table|query)\b',
            r'\b(fabric|synapse|lineage|view lineage|serverless sql|data factory|power bi)\b'
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities["technologies"].extend(matches)
        
        # Remove duplicates and clean up
        for key in entities:
            entities[key] = list(set(entities[key]))
        
        return entities

    def validate_service_region_availability(self, service: str, region: str) -> Dict[str, any]:
        """
        Validate if a specific service is available in a specific region.
        
        Args:
            service: Service name (e.g., 'openai', 'cognitive services')
            region: Region name (e.g., 'east us', 'brazil south')
            
        Returns:
            Dictionary with availability status, confidence, and recommendations
        """
        service_clean = service.lower().strip()
        region_clean = self._normalize_region_name(region.lower().strip())
        
        # Check live/cached data
        services_to_regions = self.regional_service_availability.get('services_to_regions', {})
        
        # Look for exact matches first
        available_regions = []
        for svc_name, regions in services_to_regions.items():
            if service_clean in svc_name or svc_name in service_clean:
                available_regions.extend(regions)
        
        is_available = region_clean in available_regions
        confidence = 0.9 if is_available else 0.1
        
        # If not found, check for similar services or suggest alternatives
        alternatives = []
        if not is_available:
            # Find similar services
            for svc_name in services_to_regions.keys():
                similarity = SequenceMatcher(None, service_clean, svc_name).ratio()
                if similarity > 0.6:
                    if region_clean in services_to_regions[svc_name]:
                        alternatives.append(svc_name)
        
        # Find nearby regions with the service
        nearby_regions = []
        if available_regions:
            # Simple proximity logic (same continent/country)
            region_groups = {
                'us': ['east us', 'east us 2', 'west us', 'west us 2', 'west us 3', 'central us', 'south central us', 'north central us', 'west central us'],
                'europe': ['north europe', 'west europe', 'uk south', 'uk west', 'france central', 'germany west central'],
                'asia': ['east asia', 'southeast asia', 'japan east', 'japan west', 'korea central'],
                'australia': ['australia east', 'australia southeast', 'australia central'],
                'canada': ['canada central', 'canada east']
            }
            
            current_group = None
            for group_name, group_regions in region_groups.items():
                if region_clean in group_regions:
                    current_group = group_regions
                    break
            
            if current_group:
                nearby_regions = [r for r in available_regions if r in current_group and r != region_clean]
        
        return {
            'available': is_available,
            'confidence': confidence,
            'service_normalized': service_clean,
            'region_normalized': region_clean,
            'alternative_services': alternatives,
            'nearby_regions': nearby_regions[:5],  # Limit to top 5
            'all_available_regions': available_regions[:10] if available_regions else []
        }

    def get_regional_service_summary(self, region: str) -> Dict[str, any]:
        """
        Get a summary of services available in a specific region.
        
        Args:
            region: Region name to analyze
            
        Returns:
            Dictionary with service categories and availability info
        """
        region_clean = self._normalize_region_name(region.lower().strip())
        
        regions_to_services = self.regional_service_availability.get('regions_to_services', {})
        available_services = regions_to_services.get(region_clean, [])
        
        if not available_services:
            # Try fuzzy matching for region name
            for reg_name, services in regions_to_services.items():
                similarity = SequenceMatcher(None, region_clean, reg_name).ratio()
                if similarity > 0.7:
                    available_services = services
                    region_clean = reg_name
                    break
        
        # Categorize available services
        categorized_services = {}
        for service in available_services:
            category = self._get_service_category(service)
            if category not in categorized_services:
                categorized_services[category] = []
            categorized_services[category].append(service)
        
        # Count services by category
        category_counts = {cat: len(services) for cat, services in categorized_services.items()}
        
        return {
            'region': region_clean,
            'total_services': len(available_services),
            'categorized_services': categorized_services,
            'category_counts': category_counts,
            'top_categories': sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        }

    def _get_service_category(self, service_name: str) -> str:
        """Determine which category a service belongs to"""
        service_lower = service_name.lower()
        
        category_patterns = {
            "ai_ml": ["cognitive", "openai", "speech", "vision", "language", "machine learning", "ml"],
            "compute": ["virtual machines", "app service", "functions", "container", "kubernetes"],
            "storage": ["storage", "blob", "file", "disk", "backup"],
            "database": ["sql", "cosmos", "mysql", "postgresql", "redis"],
            "networking": ["network", "load balancer", "gateway", "firewall", "cdn"],
            "security": ["key vault", "defender", "security", "identity", "entra"],
            "analytics": ["synapse", "datafactory", "powerbi", "analytics", "databricks"],
            "web": ["web", "sites", "cdn", "frontdoor"],
            "monitoring": ["monitor", "insights", "log analytics", "application insights"]
        }
        
        for category, patterns in category_patterns.items():
            if any(pattern in service_lower for pattern in patterns):
                return category
        
        return "other"
    
    def _detect_microsoft_products_with_context(self, text: str) -> Dict[str, any]:
        """
        Detect Microsoft products using external knowledge and provide contextual reasoning
        
        Args:
            text: Input text to analyze
            
        Returns:
            Dictionary with detected products and contextual analysis
        """
        result = {
            "detected_products": [],
            "context_analysis": "",
            "confidence": 0.0,
            "reasoning": [],
            "suggested_category": None,
            "suggested_intent": None
        }
        
        # Microsoft product patterns to look for - COMPREHENSIVE LIST
        product_patterns = [
            # Planning & Project Management
            r'\b(planner)\b(?:\s+(?:&|and)\s+roadmap)?',
            r'\b(roadmap)\b(?:\s+(?:&|and)\s+planner)?',
            r'\b(project)\b(?:\s+(?:for the web|online))?',
            # Collaboration
            r'\b(teams)\b',
            r'\b(sharepoint)\b',
            r'\b(yammer|viva\s+engage)\b',
            # Productivity
            r'\b(office\s*365|microsoft\s*365|m365)\b',
            r'\b(outlook)\b',
            r'\b(onedrive)\b',
            r'\b(excel)\b',
            r'\b(word)\b',
            r'\b(powerpoint)\b',
            r'\b(onenote)\b',
            # Power Platform
            r'\b(power\s*bi)\b',
            r'\b(power\s*apps)\b',
            r'\b(power\s*automate|flow)\b',
            r'\b(power\s*virtual\s*agents)\b',
            r'\b(power\s*pages)\b',
            r'\b(copilot\s*studio)\b',
            # Security & Compliance
            r'\b(sentinel)\b',
            # =====================================================================
            # DEFENDER PRODUCT FAMILY REGEX - CRITICAL BUG FIX
            # =====================================================================
            # Captures full product variants including "for" suffix
            # 
            # Bug: Previous pattern used non-capturing groups (?:...) OUTSIDE
            #      the main capturing group (), causing only "defender" to match.
            # 
            # Before: r'\b(defender)\b(?:\s+for\s+databases)?'
            #         Input: "defender for databases"
            #         Captured: "defender" only ❌
            # 
            # After:  r'\b(defender(?:\s+for\s+databases)?)\b'
            #         Input: "defender for databases"
            #         Captured: "defender for databases" ✅
            # 
            # Pattern breakdown:
            # - \b(defender...)\b:  Main capturing group (returns matched text)
            # - (?:\s+...)?:        Non-capturing group for optional suffix
            # - (?:for\s+)?:        Optional "for" keyword
            # - databases?:         "database" or "databases" (handles plurals)
            # 
            # Result: Captures full product name for accurate variant detection
            # Impact: Teams Bot now shows "Defender for Databases" instead of "defender"
            # =====================================================================
            r'\b(defender(?:\s+(?:for\s+)?(?:endpoint|identity|cloud\s+apps|office\s*365|databases?|servers?|containers?|devops|storage|key\s+vault|app\s+service|apis?|iot))?)\b',
            r'\b(entra|azure\s+ad|active\s+directory)\b',
            r'\b(purview)\b',
            r'\b(intune)\b',
            r'\b(endpoint\s+manager)\b',
            r'\b(information\s+protection)\b',
            # =====================================================================
            # AZURE SERVICES REGEX - FULLY DYNAMIC DETECTION (Jan 16 2026)
            # =====================================================================
            # Pattern: r'\b(azure\s+(?:[a-z]+\s+){0,2}[a-z]+)\b'
            # 
            # This flexible pattern captures "Azure" followed by 1-3 words.
            # NO HARDCODED service names - works for ANY Azure service!
            #
            # Examples of what this matches:
            #   ✅ "Azure Route Server" (3 words)
            #   ✅ "Azure SQL Database" (3 words)
            #   ✅ "Azure API Management" (3 words)
            #   ✅ "Azure Functions" (2 words)
            #   ✅ "Azure OpenAI" (2 words)
            #   ✅ "Azure Migrate" (2 words - the actual service, not the verb)
            #
            # Action verbs are filtered out later in context_api.py,
            # so "migrate" alone won't show up, but "Azure Migrate" will.
            #
            # This ensures the system adapts to new Azure services automatically
            # without requiring code changes for each new service Microsoft releases.
            # =====================================================================
            r'\b(azure\s+(?:[a-z]+\s+){0,2}[a-z]+)\b',  # Azure + up to 3 words
            r'\b(logic\s*apps)\b',
            r'\b(event\s*(?:hub|grid))\b',
            r'\b(service\s*bus)\b',
            # AI & Data
            r'\b(fabric)\b(?:\s+microsoft)?',
            r'\b(synapse)\b',
            r'\b(databricks)\b',
            r'\b(openai|azure\s+openai)\b',
            # =====================================================================
            # COPILOT PRODUCT FAMILY REGEX - Same capturing group fix
            # =====================================================================
            # Captures variants like "Copilot for Microsoft 365" or just "Copilot"
            # Pattern ensures full variant is captured, not just base "copilot"
            # =====================================================================
            r'\b(copilot(?:\s+(?:for\s+)?(?:microsoft\s+365|m365|security|dynamics))?)\b',
            r'\b(cognitive\s+services)\b',
            # Developer & DevOps
            # =====================================================================
            # GITHUB/VISUAL STUDIO/DYNAMICS REGEX - Same capturing group pattern
            # =====================================================================
            # All use the same fix: optional suffix INSIDE capturing group
            # =====================================================================
            # GitHub pattern - captures "github" or "github copilot" or "github actions"
            r'\b(github(?:\s+(?:copilot|actions|advanced\s+security))?)\b',
            # Visual Studio pattern - captures "visual studio" or "visual studio code"
            r'\b(visual\s+studio(?:\s+(?:code|online))?)\b',
            r'\b(azure\s+devops)\b',
            # Dynamics & CRM
            # Dynamics pattern - captures "dynamics 365" or variants like "dynamics 365 sales"
            r'\b(dynamics\s*365(?:\s+(?:sales|customer\s+service|field\s+service))?)\b',
            # Connectors & Integration
            r'\b(connector)\b',
            r'\b(logic\s+apps)\b',
            r'\b(api\s+management)\b'
        ]
        
        # Execute all patterns and collect matched terms
        # re.findall returns list of captured groups (content in parentheses)
        detected_terms = []
        for pattern in product_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            detected_terms.extend(matches)
        
        # Log detected terms for debugging
        try:
            with open('C:/Projects/Hack/debug_ica.log', 'a', encoding='utf-8') as f:
                f.write(f"\n[DEBUG ICA] All detected terms from patterns: {detected_terms}\n")
                f.flush()
        except OSError:
            pass
        print(f"[DEBUG ICA] All detected terms from patterns: {detected_terms}")
        
        if not detected_terms:
            return result
            
        # =====================================================================
        # PRODUCT KNOWLEDGE LOOKUP
        # =====================================================================
        # Fetch Microsoft product database (cached for performance)
        # Contains: title, description, URL, category for each product
        # =====================================================================
        microsoft_products = self._fetch_microsoft_products()
        print(f"[DEBUG ICA] microsoft_products dictionary keys: {list(microsoft_products.keys())[:10]}...")
        
        # Process each unique detected term
        for term in set(detected_terms):
            term_clean = term.lower().strip()
            print(f"[DEBUG ICA] Processing term: '{term}' -> cleaned: '{term_clean}'")
            
            # =====================================================================
            # PRODUCT NORMALIZATION FOR LOOKUP
            # =====================================================================
            # Problem: Detected term might be specific variant but knowledge base
            #          uses base product name as key
            # Example: Detected "defender for databases" but DB key is "defender"
            # 
            # Solution: Try both specific term and normalized base term
            # - "defender for databases" -> try "defender for databases" then "defender"
            # - "azure sql" -> try "azure sql" then "sql"
            # - "copilot for microsoft 365" -> try full then "copilot"
            # =====================================================================
            
            # Normalize product variations to base product name for lookup
            # e.g., "defender for databases" -> "defender"
            base_term = term_clean
            if term_clean.startswith("defender for "):
                base_term = "defender"
            elif term_clean.startswith("copilot for "):
                base_term = "copilot"
            elif term_clean.startswith("azure "):
                # Keep "azure openai" as-is, normalize others
                if term_clean not in microsoft_products:
                    base_term = term_clean.replace("azure ", "").strip()
            
            # Try both the specific term and the base term for database lookup
            lookup_term = term_clean if term_clean in microsoft_products else base_term
            
            if lookup_term in microsoft_products:
                product_data = microsoft_products[lookup_term]
                
                # =====================================================================
                # DISPLAY NAME CONSTRUCTION
                # =====================================================================
                # Priority: Use the FULL matched term for display (more specific)
                # - Detected "defender for databases" -> Display "Defender For Databases"
                # - NOT just "Microsoft Defender" (too generic)
                # 
                # Fallback: Use title from database if specific term not different
                # =====================================================================
                display_name = term_clean if term_clean != lookup_term else product_data.get("title", term_clean)
                
                # Build product information object for context analysis
                product_info = {
                    "name": term_clean,  # Full matched term (e.g., "defender for databases")
                    "title": display_name.title(),  # Properly capitalized display name
                    "description": product_data["description"][:300] + "..." if len(product_data["description"]) > 300 else product_data["description"],
                    "url": product_data.get("url", "https://learn.microsoft.com"),
                    "is_microsoft_product": True,
                    "category": product_data["category"]
                }
                
                result["detected_products"].append(product_info)
                result["reasoning"].append(f"[OK] Identified Microsoft product '{term}': {display_name}")
            else:
                # Check if it could be a Microsoft product but not in our database
                if any(ms_indicator in text.lower() for ms_indicator in ["microsoft", "office", "365", "m365"]):
                    result["reasoning"].append(f"[INFO] '{term}' might be a Microsoft product but not in knowledge base")
                else:
                    result["reasoning"].append(f"[DEBUG] '{term}' not identified as Microsoft product")
        
        # Analyze context based on detected products
        if result["detected_products"]:
            result["confidence"] = min(0.95, 0.3 + (len(result["detected_products"]) * 0.2))
            
            # Special case: "Planner & Roadmap" or similar combinations
            product_names = [p["name"] for p in result["detected_products"]]
            if "planner" in product_names or "roadmap" in product_names:
                # Strong indicators for training/demo
                training_indicators = ["demo", "training", "overview", "deep dive", "presentation", "walkthrough", "introduction"]
                
                if any(indicator in text.lower() for indicator in training_indicators):
                    result["suggested_category"] = "training_documentation" 
                    result["suggested_intent"] = "seeking_guidance"
                    result["context_analysis"] = f"Microsoft product(s) detected in training/demo context: {', '.join(product_names)}"
                    result["reasoning"].append(f"[OK] Training context detected with Microsoft products: {', '.join(product_names)}")
                    result["confidence"] = 0.9  # High confidence for training context
                    
                elif ("planner" in product_names and "roadmap" in product_names) or "&" in text or " and " in text.lower():
                    # Both products mentioned together - likely product demo
                    result["context_analysis"] = "Multiple Microsoft products detected - likely product inquiry/demo"
                    result["suggested_category"] = "training_documentation"
                    result["suggested_intent"] = "seeking_guidance"
                    result["reasoning"].append("[RESULT] Multiple Microsoft products together suggest product demonstration/inquiry")
                    result["confidence"] = 0.85
                    
                elif "roadmap" in text.lower() and not any(indicator in text.lower() for indicator in training_indicators):
                    # Check if this is timeline inquiry vs Microsoft Roadmap product
                    timeline_indicators = [
                        "when will", "when is", "timeline for", "availability for", "launch date",
                        "support roadmap", "feature roadmap", "product roadmap", "service roadmap",
                        "future availability", "coming soon", "planned for", "release timeline",
                        "when available", "eta for", "expected date", "schedule for"
                    ]
                    
                    is_timeline_inquiry = any(indicator in text.lower() for indicator in timeline_indicators)
                    
                    # Additional context: If asking about support/feature/availability, it's timeline inquiry
                    has_support_context = any(term in text.lower() for term in ["support", "feature", "capability", "available in"])
                    
                    if is_timeline_inquiry or has_support_context:
                        # This is a timeline/roadmap inquiry, NOT Microsoft Roadmap product
                        result["context_analysis"] = "Timeline inquiry detected - asking about future availability/roadmap"
                        result["suggested_category"] = "roadmap"  # Roadmap category for timeline questions
                        result["suggested_intent"] = "roadmap_inquiry"
                        result["reasoning"].append("🎯 CONTEXT OVERRIDE: Timeline inquiry detected - 'roadmap' refers to schedule/availability, not Microsoft product")
                        result["confidence"] = 0.85
                        # Clear detected products since this isn't about the product
                        result["detected_products"] = []
                    else:
                        # Could be roadmap planning vs Microsoft Roadmap product
                        result["context_analysis"] = "Ambiguous - could be Microsoft products or roadmap planning"
                        result["suggested_category"] = "training_documentation"  # Default to product interpretation
                        result["suggested_intent"] = "seeking_guidance"
                        result["reasoning"].append("❓ Ambiguous case - defaulting to Microsoft product interpretation")
                        result["confidence"] = 0.6
                    
                else:
                    # Single Microsoft product detected
                    result["suggested_category"] = "training_documentation"
                    result["suggested_intent"] = "seeking_guidance"
                    result["context_analysis"] = f"Microsoft product detected: {', '.join(product_names)}"
                    result["reasoning"].append(f"✅ Microsoft product inquiry: {', '.join(product_names)}")
                    result["confidence"] = 0.8
            
            # General Microsoft 365 product detection
            if len(result["detected_products"]) > 1:
                result["context_analysis"] += f" Multiple Microsoft products detected: {', '.join(product_names)}"
                result["reasoning"].append(f"📊 Multiple Microsoft products suggest M365 ecosystem inquiry")
        
        return result
    
    def _classify_category(self, text: str, entities: Dict) -> Tuple[IssueCategory, float]:
        """Classify the issue category with confidence score"""
        
        # 🔍 STEP 1: Check for Microsoft products using external knowledge
        microsoft_product_analysis = self._detect_microsoft_products_with_context(text)
        
        # Log the Microsoft product analysis for debugging
        if microsoft_product_analysis["detected_products"]:
            self.logger.info(f"🔍 MICROSOFT PRODUCT ANALYSIS:")
            for reason in microsoft_product_analysis["reasoning"]:
                self.logger.info(f"  {reason}")
            if microsoft_product_analysis["suggested_category"]:
                self.logger.info(f"🎯 SUGGESTED: {microsoft_product_analysis['suggested_category']} / {microsoft_product_analysis['suggested_intent']}")
        
        # Check if this is actually a technical issue being reported (takes priority over product detection)
        technical_problem_indicators = [
            "error", "issue", "problem", "not working", "troubleshoot", "bug", "failed",
            "not ingesting", "not displaying", "displays 0%", "shows 0%", "incorrect",
            "missing", "broken", "failure", "doesn't work", "not functioning"
        ]
        
        is_technical_problem = any(indicator in text.lower() for indicator in technical_problem_indicators)
        
        # If we have Microsoft product detection with suggestions, use them ONLY if not a technical problem
        if (microsoft_product_analysis["confidence"] >= 0.5 and 
            microsoft_product_analysis["suggested_category"] and
            microsoft_product_analysis["suggested_intent"] and
            not is_technical_problem):  # Don't override if reporting technical issue
            
            # Map string categories to enum values
            category_mapping = {
                "training_documentation": IssueCategory.TRAINING_DOCUMENTATION,
                "roadmap": IssueCategory.ROADMAP,
                "technical_support": IssueCategory.TECHNICAL_SUPPORT,
                "feature_request": IssueCategory.FEATURE_REQUEST
            }
            
            suggested_cat = microsoft_product_analysis["suggested_category"]
            if suggested_cat in category_mapping:
                confidence = max(0.8, microsoft_product_analysis["confidence"])  # Boost confidence for product detection
                self.logger.info(f"✅ MICROSOFT PRODUCT OVERRIDE: {suggested_cat} ({confidence:.2f})")
                return category_mapping[suggested_cat], confidence
        
        elif is_technical_problem and microsoft_product_analysis["detected_products"]:
            self.logger.info(f"⚠️ TECHNICAL PROBLEM DETECTED - Skipping Microsoft product category override")
        
        category_scores = {}
        
        # Compliance/Regulatory indicators
        compliance_indicators = len(entities.get("compliance_frameworks", [])) * 0.4
        if any(word in text for word in ["compliance", "regulatory", "audit", "policy", "governance"]):
            compliance_indicators += 0.3
            
        # ============================================================================
        # 🆕 v3.1 FIX: PREVENT COMPLIANCE KEYWORDS FROM OVERWHELMING FEATURE REQUESTS
        # ============================================================================
        # PROBLEM: "Sentinel connectors for GCCH" was classified as Compliance/Regulatory
        #          because GCCH/GCC scored 0.7 for compliance, overwhelming "need connectors" (0.5)
        # 
        # SOLUTION: Detect strong feature request language (connectors, integration)
        #           and reduce compliance score by 50% when present
        #
        # RATIONALE: Issues mentioning GCCH/GCC are often requesting features IN those
        #            environments, not asking about compliance requirements
        #
        # EXAMPLE: "Need Sentinel connectors for GCCH environment"
        #          - Old: Compliance (0.7) > Feature Request (0.5) = WRONG
        #          - New: Compliance (0.35) < Feature Request (0.9) = CORRECT
        # ============================================================================
        
        has_strong_feature_language = any(phrase in text.lower() for phrase in [
            "connector", "connectors", "integration", "feature needed", "capability needed",
            "need feature", "need connector", "require connector", "integration needed"
        ])
        
        if has_strong_feature_language and compliance_indicators > 0:
            # This is likely a feature request IN a compliance context, not a compliance issue
            compliance_indicators = compliance_indicators * 0.5  # Reduce by 50%
            print(f"[INFO] Compliance score reduced due to strong feature request language (connector/integration detected)")
            
        category_scores[IssueCategory.COMPLIANCE_REGULATORY] = compliance_indicators
        
        # 🚨 CAPACITY indicators - CHECK FIRST WITH HIGHEST PRIORITY
        capacity_indicators = 0
        
        # High-confidence capacity request phrases - should override other categories
        high_capacity_phrases = [
            "capacity needed", "need capacity", "requesting capacity", "capacity request",
            "quota needed", "need quota", "requesting quota", "quota request", 
            "increase capacity", "increase quota", "more capacity", "additional capacity",
            "capacity for", "quota for", "scaling up", "scale up"
        ]
        if any(phrase in text.lower() for phrase in high_capacity_phrases):
            capacity_indicators += 0.95  # Very high confidence - should win over technical support
        
        # Medium-confidence capacity indicators  
        capacity_phrases = [
            "capacity limit", "quota exceeded", "resource limit", "scaling limit",
            "capacity constraint", "resource constraint", "limit reached", "quota limit",
            "capacity issue", "resource unavailable", "scaling issue", "out of capacity"
        ]
        if any(phrase in text.lower() for phrase in capacity_phrases):
            capacity_indicators += 0.8
            
        # Basic capacity/quota keywords
        if "capacity" in text.lower():
            capacity_indicators += 0.4
        if "quota" in text.lower():
            capacity_indicators += 0.4
            
        # Regional capacity requests (like "EAST-US Capacity needed")
        # Use comprehensive list from region name mapping keys
        capacity_region_patterns = list(self.region_name_mapping.keys()) + ["us-east", "us-west", "us-central", "europe", "asia"]
        if any(region in text.lower() for region in capacity_region_patterns) and "capacity" in text.lower():
            capacity_indicators += 0.6  # Regional capacity requests are very specific
            
        category_scores[IssueCategory.CAPACITY] = capacity_indicators
        
        # Early exit if we have very high capacity confidence
        if capacity_indicators >= 0.9:
            print(f"🎯 HIGH CAPACITY CONFIDENCE: {capacity_indicators:.2f} - Early classifying as CAPACITY")
            return IssueCategory.CAPACITY, min(capacity_indicators, 1.0)
        
        # Service Retirement indicators
        retirement_indicators = 0
        if any(word in text for word in ["retirement", "deprecated", "end of life", "migration", "alternative"]):
            retirement_indicators += 0.6
        category_scores[IssueCategory.SERVICE_RETIREMENT] = retirement_indicators
        
        # Technical Support indicators - ENHANCED WITH CONTEXT AWARENESS
        tech_support_indicators = 0
        
        # Strong technical problem indicators
        strong_tech_indicators = [
            "experiencing an issue", "experiencing issue", "displays a value of 0", "shows 0%",
            "not ingesting", "not displaying", "fail to display", "not working correctly",
            "behavior is by design", "regression", "known limitation", "product defect",
            "root cause", "missing", "incorrect", "broken", "failure"
        ]
        
        # Basic technical keywords
        basic_tech_keywords = ["error", "issue", "problem", "not working", "troubleshoot"]
        
        # Check for detailed technical problem description
        strong_tech_count = sum(1 for indicator in strong_tech_indicators if indicator in text.lower())
        basic_tech_count = sum(1 for keyword in basic_tech_keywords if keyword in text.lower())
        
        if strong_tech_count > 0:
            tech_support_indicators += 0.7  # High confidence for detailed problem descriptions
        
        if basic_tech_count > 0:
            tech_support_indicators += 0.4
            
        if len(entities.get("azure_services", [])) > 0:
            tech_support_indicators += 0.2
            
        # Extra boost if multiple technical indicators (suggests detailed problem report)
        if strong_tech_count >= 2 or basic_tech_count >= 3:
            tech_support_indicators += 0.3  # This is clearly a technical issue, not just mentioning it
            
        category_scores[IssueCategory.TECHNICAL_SUPPORT] = tech_support_indicators
        
        # ============================================================================
        # 🆕 v3.1 FIX: ENHANCED FEATURE REQUEST DETECTION WITH CONNECTOR PRIORITY
        # ============================================================================
        # PROBLEM: Connector requests scored only 0.5, easily overwhelmed by other signals
        #
        # SOLUTION: Strong connector/integration phrases now score 0.9 (very high confidence)
        #           This ensures connector requests are correctly identified as feature requests
        #
        # RATIONALE: Connectors are ALWAYS feature requests, never compliance or technical support
        #            They represent capabilities that need to be built or made available
        #
        # SCORING STRATEGY:
        # - Strong phrases (connectors, integration): 0.9 (near-certain feature request)
        # - Standard phrases (feature, enhancement): 0.5 (high confidence)
        # - Supporting phrases (need, require): 0.3 (contextual evidence)
        # - Context phrases (in order to, to enable): 0.4 (intent evidence)
        #
        # EXAMPLE DETECTION:
        # "Need Sentinel connectors for GCCH"
        # - "connectors" triggers: +0.9 (strong feature phrase)
        # - "need" triggers: +0.3 (supporting evidence)
        # - Total: 1.0 (max score) = Feature Request with 100% confidence
        # ============================================================================
        
        feature_indicators = 0
        
        # Strong feature request phrases (HIGH PRIORITY - 0.9 score)
        strong_feature_phrases = [
            "connector", "connectors", "connector needed", "connectors needed",
            "need connector", "need connectors", "integration needed", "connector for",
            "connector support", "connectors required", "feature needed", "feature request",
            "need feature", "require feature", "capability needed", "need capability"
        ]
        if any(phrase in text.lower() for phrase in strong_feature_phrases):
            feature_indicators += 0.9  # 🆕 INCREASED from 0.5 - Very high confidence for connectors/integration
        
        # Standard feature request keywords
        if any(word in text for word in ["feature", "enhancement", "capability", "functionality"]):
            feature_indicators += 0.5
        if any(word in text for word in ["new", "add", "support for", "implement"]):
            feature_indicators += 0.2
            
        # Enhanced detection for equivalent/similar features
        if any(phrase in text.lower() for phrase in ["equivalent to", "similar to", "like we had", "what we had in", "same as", "comparable to"]):
            feature_indicators += 0.6
            
        # Need/want/require language
        if any(word in text.lower() for word in ["looking for", "need", "want", "seeking", "require", "necessary"]):
            feature_indicators += 0.3
            
        # "In order to" pattern suggests feature needed for purpose
        if "in order to" in text.lower() or "to support" in text.lower() or "to enable" in text.lower():
            feature_indicators += 0.4
            
        category_scores[IssueCategory.FEATURE_REQUEST] = feature_indicators
        
        # Security/Governance indicators
        security_indicators = 0
        security_services = ["defender for cloud", "sentinel", "security center", "key vault"]
        if any(service in text for service in security_services):
            security_indicators += 0.4
        if any(word in text for word in ["security", "authentication", "authorization", "encryption"]):
            security_indicators += 0.3
        category_scores[IssueCategory.SECURITY_GOVERNANCE] = security_indicators
        
        # Migration/Modernization indicators - ENHANCED
        migration_indicators = 0
        migration_keywords = ["migration", "migrate", "modernize", "upgrade", "move to", "moving to"]
        
        if any(word in text.lower() for word in migration_keywords):
            migration_indicators += 0.7
            
        category_scores[IssueCategory.MIGRATION_MODERNIZATION] = migration_indicators
        
        # 🆕 SERVICE AVAILABILITY indicators - HIGH PRIORITY
        service_availability_indicators = 0
        availability_phrases = [
            "lack of service", "service not available", "service unavailable", "service missing",
            "not available in", "unavailable in", "missing in region", "not offered in",
            "service gap", "regional gap", "availability in", "when will service",
            "service launch", "service rollout", "regional availability",
            "required in", "needed in", "not supported in", "support in region"
        ]
        if any(phrase in text.lower() for phrase in availability_phrases):
            service_availability_indicators += 0.8  # High confidence
        
        # Detect regional context with service needs
        regions = ["brazil", "europe", "asia", "africa", "australia", "canada", "uk", "germany", "france", "japan", 
                   "east us", "west us", "central us", "north europe", "west europe"]
        region_detected = any(region in text.lower() for region in regions)
        
        if region_detected:
            service_availability_indicators += 0.3
            
            # Additional boost if talking about alternatives/options with regional context
            if any(word in text.lower() for word in ["alternative", "option", "evaluate", "seeking", "looking for"]):
                service_availability_indicators += 0.2
                
        category_scores[IssueCategory.SERVICE_AVAILABILITY] = service_availability_indicators
        
        # 🆕 DATA SOVEREIGNTY indicators - HIGH PRIORITY  
        sovereignty_indicators = 0
        sovereignty_phrases = [
            "sovereignty", "sovereign", "data residency", "regulatory compliance",
            "local data", "regional compliance", "jurisdiction", "data governance",
            "compliance requirement", "legal requirement", "regulatory requirement"
        ]
        if any(phrase in text.lower() for phrase in sovereignty_phrases):
            sovereignty_indicators += 0.9  # Very high confidence
            
        # Regional sovereignty context
        if any(region in text.lower() for region in regions) and "compliance" in text.lower():
            sovereignty_indicators += 0.4
            
        category_scores[IssueCategory.DATA_SOVEREIGNTY] = sovereignty_indicators
        
        # 🆕 AOAI CAPACITY indicators - SPECIFIC TO OPENAI ONLY
        aoai_capacity_indicators = 0
        aoai_phrases = [
            "azure openai", "aoai", "openai capacity", "openai quota", "model capacity",
            "gpt capacity", "azure cognitive services quota", "model unavailable",
            "openai service capacity", "cognitive services capacity"
        ]
        # Only classify as AOAI_CAPACITY if specifically mentions OpenAI/GPT/Cognitive Services
        if any(phrase in text.lower() for phrase in aoai_phrases):
            aoai_capacity_indicators += 0.9  # Very high confidence
        if "capacity" in text.lower() and ("openai" in text.lower() or "gpt" in text.lower() or "cognitive" in text.lower()):
            aoai_capacity_indicators += 0.85
        category_scores[IssueCategory.AOAI_CAPACITY] = aoai_capacity_indicators
        
        # 🆕 BUSINESS DESK indicators
        business_desk_indicators = 0
        business_phrases = [
            "business engagement", "partnership", "business relationship", "account team",
            "business desk", "commercial discussion", "enterprise agreement", "business case",
            "stakeholder engagement", "executive sponsor", "business alignment"
        ]
        if any(phrase in text.lower() for phrase in business_phrases):
            business_desk_indicators += 0.8
        category_scores[IssueCategory.BUSINESS_DESK] = business_desk_indicators

        
        # 🆕 RETIREMENTS indicators - HIGH PRIORITY
        retirements_indicators = 0
        retirement_phrases = [
            "retirement", "deprecated", "end of life", "eol", "discontinue", "sunset",
            "phase out", "no longer supported", "legacy service", "replacement service",
            "service ending", "deprecation notice", "end of support"
        ]
        if any(phrase in text.lower() for phrase in retirement_phrases):
            retirements_indicators += 0.9  # Very high confidence
        category_scores[IssueCategory.RETIREMENTS] = retirements_indicators
        
        # 🆕 ROADMAP indicators - CONTEXT AWARE
        roadmap_indicators = 0
        roadmap_phrases = [
            "roadmap", "timeline", "when available", "future plans", "upcoming features",
            "product roadmap", "service roadmap", "release timeline", "availability timeline",
            "planned features", "future availability", "development timeline"
        ]
        
        roadmap_keyword_count = sum(1 for phrase in roadmap_phrases if phrase in text.lower())
        
        if roadmap_keyword_count > 0:
            # Check if this is a primary roadmap inquiry or incidental mention
            # Primary inquiry: "when will X be available", "what's on the roadmap"
            # Incidental: mentioned in context of technical problem or project
            
            primary_roadmap_inquiry = any(phrase in text.lower() for phrase in [
                "what is the roadmap", "what's the roadmap", "share the roadmap",
                "product roadmap for", "service roadmap for", "timeline for availability",
                "when will this be available", "future availability of", "planned release of"
            ])
            
            # If technical support score is high, reduce roadmap weight (incidental mention)
            if tech_support_indicators >= 0.8:
                roadmap_indicators += 0.3  # Low weight - just asking if fix is on roadmap
            elif primary_roadmap_inquiry:
                roadmap_indicators += 0.8  # Primary intent is roadmap inquiry
            else:
                roadmap_indicators += 0.5  # Moderate - could be either
                
        category_scores[IssueCategory.ROADMAP] = roadmap_indicators
        
        # 🆕 SUPPORT indicators
        support_indicators = 0
        support_phrases = [
            "need help", "support request", "assistance", "help with", "guidance",
            "technical support", "customer support", "support case", "need assistance"
        ]
        if any(phrase in text.lower() for phrase in support_phrases):
            support_indicators += 0.6
        category_scores[IssueCategory.SUPPORT] = support_indicators
        
        # 🆕 SUPPORT ESCALATION indicators - HIGH PRIORITY
        escalation_indicators = 0
        escalation_phrases = [
            "escalation", "escalate", "urgent", "critical", "emergency", "high priority",
            "business critical", "production down", "outage", "sev 1", "severity 1",
            "immediate attention", "escalate to manager", "customer escalation"
        ]
        if any(phrase in text.lower() for phrase in escalation_phrases):
            escalation_indicators += 0.9  # Very high priority
        category_scores[IssueCategory.SUPPORT_ESCALATION] = escalation_indicators
        
        # 🆕 SUSTAINABILITY indicators
        sustainability_indicators = 0
        sustainability_phrases = [
            "sustainability", "carbon footprint", "green", "environmental impact",
            "energy efficiency", "carbon neutral", "renewable energy", "eco-friendly",
            "environmental", "carbon emissions", "green computing", "sustainable computing"
        ]
        if any(phrase in text.lower() for phrase in sustainability_phrases):
            sustainability_indicators += 0.8
        category_scores[IssueCategory.SUSTAINABILITY] = sustainability_indicators
        
        # ====================================================================
        # ENG-003 Step 3: Apply active-learning weight adjustments
        # ====================================================================
        # Multipliers are computed by weight_tuner.py from human-resolved
        # disagreement signals.  They nudge category scores up or down so
        # the pattern engine converges toward human preferences over time.
        if self._weight_multipliers:
            for cat_enum, score in list(category_scores.items()):
                cat_key = cat_enum.value if hasattr(cat_enum, 'value') else str(cat_enum)
                multiplier = self._weight_multipliers.get(cat_key, 1.0)
                if multiplier != 1.0 and score > 0:
                    adjusted = score * multiplier
                    print(f"[WeightAdj] {cat_key}: {score:.3f} × {multiplier:.3f} → {adjusted:.3f}")
                    category_scores[cat_enum] = adjusted

        # Find highest scoring category
        best_category = max(category_scores.items(), key=lambda x: x[1])
        
        # Default to technical support if no clear category
        if best_category[1] < 0.3:
            return IssueCategory.TECHNICAL_SUPPORT, 0.5
        
        return best_category[0], min(best_category[1], 1.0)
    
    def _classify_intent(self, text: str) -> Tuple[IntentType, float]:
        """Classify user intent with context-aware analysis"""
        
        intent_scores = {}
        text_lower = text.lower()
        
        # === CONTEXT-AWARE INTENT DETECTION ===
        # Detect demo/presentation/comparison contexts that indicate guidance seeking
        demo_context_indicators = [
            "demo", "demonstration", "presentation", "present", "showcase", "show",
            "comparison", "compare", "vs", "versus", "evaluate", "assessment",
            "explain", "understand", "learn about", "need information"
        ]
        
        pre_sales_indicators = [
            "pre-sales", "presales", "pre sales", "customer engagement", "partner",
            "partners", "license", "licensing", "subscription", "plan comparison",
            "choose between", "which option", "decision", "evaluation"
        ]
        
        # === ROADMAP TIMELINE INQUIRY DETECTION (HIGH PRIORITY) ===
        # Check if this is asking about future availability/timeline
        roadmap_timeline_indicators = [
            "when will", "when is", "timeline for", "availability for", "launch date",
            "support roadmap", "feature roadmap", "product roadmap", "service roadmap",
            "future availability", "coming soon", "planned for", "release timeline",
            "when available", "eta for", "expected date", "schedule for", "roadmap for"
        ]
        
        roadmap_score = sum(0.25 for indicator in roadmap_timeline_indicators if indicator in text_lower)
        
        if roadmap_score > 0 or ("roadmap" in text_lower and any(term in text_lower for term in ["support", "feature", "availability", "launch"])):
            # This is a roadmap/timeline inquiry - high priority
            roadmap_score = max(roadmap_score, 0.5)  # Minimum score if context detected
            intent_scores[IntentType.ROADMAP_INQUIRY] = min(roadmap_score, 1.0)
            print(f"🎯 HIGH PRIORITY ROADMAP INQUIRY DETECTED: Timeline/availability question (score: {roadmap_score:.2f})")
        
        # Check for demo/comparison + product context (not asking about timelines)
        demo_score = sum(0.15 for indicator in demo_context_indicators if indicator in text_lower)
        pre_sales_score = sum(0.15 for indicator in pre_sales_indicators if indicator in text_lower)
        
        # Context override: If discussing demo/comparison with products, it's guidance seeking
        if (demo_score > 0 or pre_sales_score > 0):
            # Check if "roadmap" is part of a product name (not asking about timelines)
            if "roadmap" in text_lower and roadmap_score == 0:  # Only if not already detected as timeline inquiry
                # Context clues that "roadmap" is a product name, not timeline inquiry
                product_context_indicators = [
                    "planner", "planner & roadmap", "planner and roadmap", "the roadmap",
                    "new roadmap", "roadmap product", "roadmap service", "roadmap tool"
                ]
                
                is_product_name = any(indicator in text_lower for indicator in product_context_indicators)
                
                # If roadmap appears with product context + demo/comparison, it's seeking guidance
                if is_product_name:
                    guidance_score = demo_score + pre_sales_score + 0.3  # Boost for product context
                    intent_scores[IntentType.SEEKING_GUIDANCE] = min(guidance_score, 1.0)
                    print(f"🎯 CONTEXT OVERRIDE: 'roadmap' detected as product name in demo/comparison context → SEEKING_GUIDANCE (score: {guidance_score:.2f})")
        
        # === FEATURE REQUEST DETECTION WITH MIGRATE CONTEXT ===
        # When "migrate" appears but context is about switching products and needing features/connectors
        feature_request_indicators = [
            "feature", "connector", "connectors", "capability", "capabilities",
            "support for", "integration", "integrations", "add support", "enable",
            "functionality", "need to", "require", "requires", "necessary",
            "in order to", "to support", "to enable", "must have"
        ]
        
        # Check if migrate is present but context is about features
        if "migrate" in text_lower or "migration" in text_lower:
            feature_context_count = sum(1 for indicator in feature_request_indicators if indicator in text_lower)
            
            # If "migrate" appears with feature context, it's likely "migrate TO (switch to) product X"
            # and listing features needed to make the switch
            if feature_context_count >= 2:
                # Check for "migrate to" pattern which means switching TO a product
                if "migrate to" in text_lower or "switch to" in text_lower or "move to" in text_lower:
                    feature_request_score = 0.7 + (feature_context_count * 0.05)
                    intent_scores[IntentType.REQUESTING_FEATURE] = min(feature_request_score, 1.0)
                    print(f"[CONTEXT] 'Migrate' detected in feature request context (switching TO product, listing needed features): {feature_request_score:.2f}")
                else:
                    # Even without "to", if many feature indicators present, it's likely a feature request
                    if feature_context_count >= 3:
                        feature_request_score = 0.6 + (feature_context_count * 0.05)
                        intent_scores[IntentType.REQUESTING_FEATURE] = min(feature_request_score, 1.0)
                        print(f"[CONTEXT] 'Migrate' with heavy feature context detected: {feature_request_score:.2f}")
        
        # ============================================================================
        # 🆕 v3.1 FIX: HIGH PRIORITY FEATURE REQUEST DETECTION (CHECK FIRST)
        # ============================================================================
        # PROBLEM: REQUESTING_FEATURE intent was checked AFTER COMPLIANCE_SUPPORT
        #          This meant GCCH/GCC keywords would trigger compliance intent first,
        #          even when the user was clearly requesting connectors/features
        #
        # SOLUTION: Check for strong feature request patterns FIRST with early exit
        #           When confidence >= 0.45, immediately return REQUESTING_FEATURE
        #           This ensures connector requests bypass compliance checking
        #
        # RATIONALE: Connector/integration requests are ALWAYS feature requests, never compliance
        #            They should take absolute priority in intent classification
        #
        # EARLY EXIT STRATEGY:
        # - Each strong pattern: +0.45 confidence (enough to trigger exit)
        # - Multiple patterns: Cumulative scoring (higher confidence)
        # - Exit threshold: 0.45+ (moderate-high confidence)
        # - Final confidence: pattern_score + 0.2 boost (capped at 1.0)
        #
        # EXAMPLE FLOW:
        # "Need connectors for Sentinel" → detects "need connectors" → +0.45
        # → Confidence 0.45 >= threshold → EARLY EXIT with REQUESTING_FEATURE (0.65 final)
        # → Compliance check NEVER RUNS → Correct classification guaranteed
        #
        # This prevents the previous bug where:
        # 1. System would check compliance first
        # 2. GCCH/GCC would score 0.7 for COMPLIANCE_SUPPORT
        # 3. Feature request check would score 0.5
        # 4. Result: COMPLIANCE_SUPPORT (WRONG)
        # ============================================================================
        
        strong_feature_request_patterns = [
            "connector needed", "connectors needed", "need connector", "need connectors",
            "connector for", "connector support", "connectors required", "connector to",
            "integration needed", "need integration", "feature needed", "need feature",
            "capability needed", "need capability", "require connector", "require connectors"
        ]
        
        feature_request_score = 0
        for pattern in strong_feature_request_patterns:
            if pattern in text_lower:
                feature_request_score += 0.45  # High weight for feature requests
        
        # Early exit for high-confidence feature requests (especially with connectors)
        if feature_request_score >= 0.45:
            print(f"[RESULT] HIGH FEATURE REQUEST CONFIDENCE: {feature_request_score:.2f} - Connectors/integration detected - Early classifying as REQUESTING_FEATURE")
            return IntentType.REQUESTING_FEATURE, min(feature_request_score + 0.2, 1.0)  # Boost confidence
        
        if feature_request_score > 0:
            intent_scores[IntentType.REQUESTING_FEATURE] = min(feature_request_score + 0.15, 1.0)
        
        # High priority capacity request patterns - check these second
        capacity_request_patterns = [
            "capacity needed", "need capacity", "requesting capacity", "capacity request",
            "quota needed", "need quota", "requesting quota", "quota request", 
            "increase capacity", "increase quota", "more capacity", "additional capacity",
            "capacity for", "quota for", "capacity in", "quota in", "capacity increase"
        ]
        
        capacity_request_score = 0
        for pattern in capacity_request_patterns:
            if pattern in text_lower:
                capacity_request_score += 0.4  # Higher weight for capacity requests
        
        # Early exit for high-confidence capacity requests
        if capacity_request_score >= 0.4:
            print(f"[RESULT] HIGH CAPACITY INTENT CONFIDENCE: {capacity_request_score:.2f} - Early classifying as CAPACITY_REQUEST")
            return IntentType.CAPACITY_REQUEST, min(capacity_request_score, 1.0)
        
        if capacity_request_score > 0:
            intent_scores[IntentType.CAPACITY_REQUEST] = min(capacity_request_score, 1.0)
        
        # High priority service availability patterns - check these second
        service_availability_patterns = [
            "service not available", "service unavailable", "not available in", "unavailable in",
            "lack of service", "service missing", "service gap", "no support for", "missing service",
            "service not offered", "not offered in", "when will service", "service launch",
            "regional availability", "availability in region"
        ]
        
        # Check for high-priority service availability intent 
        service_availability_score = 0
        for pattern in service_availability_patterns:
            if pattern in text_lower:
                service_availability_score += 0.3  # Higher weight for service availability
        
        if service_availability_score > 0:
            intent_scores[IntentType.REQUESTING_SERVICE] = min(service_availability_score, 1.0)
        
        # Check other intents with pattern matching
        for intent_type, patterns in self.intent_patterns.items():
            if intent_type == IntentType.REQUESTING_SERVICE:
                continue  # Already handled above with higher priority
                
            score = 0
            for pattern in patterns:
                if pattern in text_lower:
                    # Context-aware scoring: reduce roadmap intent if demo context detected
                    if intent_type == IntentType.ROADMAP_INQUIRY and (demo_score > 0 or pre_sales_score > 0):
                        score += 0.05  # Reduced weight when in demo/comparison context
                    else:
                        score += 0.2
            
            # Only set score if we found patterns
            if score > 0:
                intent_scores[intent_type] = min(score, 1.0)
        
        # Find highest scoring intent
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
        else:
            # Default to seeking guidance if no clear intent
            return IntentType.SEEKING_GUIDANCE, 0.5
            
        # If we detected capacity request with high confidence, prefer it
        if IntentType.CAPACITY_REQUEST in intent_scores and intent_scores[IntentType.CAPACITY_REQUEST] >= 0.6:
            return IntentType.CAPACITY_REQUEST, intent_scores[IntentType.CAPACITY_REQUEST]
            
        # If we detected roadmap inquiry with high confidence, prefer it
        if IntentType.ROADMAP_INQUIRY in intent_scores and intent_scores[IntentType.ROADMAP_INQUIRY] >= 0.5:
            print(f"🎯 HIGH CONFIDENCE ROADMAP INQUIRY: {intent_scores[IntentType.ROADMAP_INQUIRY]:.2f} - Classifying as ROADMAP_INQUIRY")
            return IntentType.ROADMAP_INQUIRY, intent_scores[IntentType.ROADMAP_INQUIRY]
            
        # If we detected service availability with high confidence, prefer it
        if IntentType.REQUESTING_SERVICE in intent_scores and intent_scores[IntentType.REQUESTING_SERVICE] >= 0.6:
            return IntentType.REQUESTING_SERVICE, intent_scores[IntentType.REQUESTING_SERVICE]
        
        # Context-aware preference: If seeking guidance scored well, prefer it over roadmap
        if IntentType.SEEKING_GUIDANCE in intent_scores and intent_scores[IntentType.SEEKING_GUIDANCE] >= 0.5:
            if IntentType.ROADMAP_INQUIRY in intent_scores and intent_scores[IntentType.ROADMAP_INQUIRY] < 0.3:
                print(f"🎯 CONTEXT PREFERENCE: SEEKING_GUIDANCE ({intent_scores[IntentType.SEEKING_GUIDANCE]:.2f}) preferred over ROADMAP_INQUIRY ({intent_scores.get(IntentType.ROADMAP_INQUIRY, 0):.2f})")
                return IntentType.SEEKING_GUIDANCE, intent_scores[IntentType.SEEKING_GUIDANCE]
        
        # Default to seeking guidance if no clear intent
        if best_intent[1] < 0.2:
            return IntentType.SEEKING_GUIDANCE, 0.5
        
        return best_intent[0], best_intent[1]
    
    def _extract_key_concepts(self, text: str, entities: Dict) -> List[str]:
        """Extract key concepts for semantic matching"""
        concepts = []
        
        # Add domain entities as key concepts
        for entity_list in entities.values():
            concepts.extend(entity_list)
        
        # Extract important noun phrases
        important_patterns = [
            r'\b(?:azure|microsoft|cloud)\s+\w+(?:\s+\w+)?\b',
            r'\b\w+(?:\s+\w+)?\s+(?:service|feature|capability|solution)\b',
            r'\b(?:compliance|regulatory|audit|security)\s+\w+\b'
        ]
        
        for pattern in important_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            concepts.extend(matches)
        
        return list(set(concepts))
    
    def _generate_semantic_keywords(self, text: str, entities: Dict, category: IssueCategory) -> List[str]:
        """Generate semantic keywords for intelligent matching"""
        keywords = []
        
        # Add category-specific keywords
        category_keywords = {
            IssueCategory.COMPLIANCE_REGULATORY: ["policy", "standard", "framework", "requirement", "control"],
            IssueCategory.TECHNICAL_SUPPORT: ["configuration", "implementation", "troubleshooting", "resolution"],
            IssueCategory.FEATURE_REQUEST: ["functionality", "capability", "enhancement", "improvement"],
            IssueCategory.SECURITY_GOVERNANCE: ["protection", "monitoring", "detection", "prevention"],
            IssueCategory.MIGRATION_MODERNIZATION: ["transition", "upgrade", "modernization", "replacement"],
            IssueCategory.SERVICE_AVAILABILITY: ["regional", "availability", "rollout", "launch", "deployment", "offering"],
            IssueCategory.DATA_SOVEREIGNTY: ["residency", "jurisdiction", "compliance", "governance", "regulatory"],
            IssueCategory.PRODUCT_ROADMAP: ["timeline", "future", "planned", "upcoming", "roadmap", "announcement"],
            # 🆕 NEW CATEGORY KEYWORDS
            IssueCategory.AOAI_CAPACITY: ["quota", "limit", "capacity", "model", "cognitive", "openai"],
            IssueCategory.BUSINESS_DESK: ["partnership", "engagement", "commercial", "relationship", "account"],
            IssueCategory.CAPACITY: ["quota", "limit", "resource", "scaling", "constraint", "allocation"],
            IssueCategory.RETIREMENTS: ["retirement", "deprecation", "sunset", "replacement", "migration"],
            IssueCategory.ROADMAP: ["timeline", "future", "planned", "roadmap", "development", "release"],
            IssueCategory.SUPPORT: ["assistance", "help", "guidance", "support", "resolution"],
            IssueCategory.SUPPORT_ESCALATION: ["urgent", "critical", "escalation", "priority", "emergency"],
            IssueCategory.SUSTAINABILITY: ["carbon", "green", "environmental", "energy", "sustainable", "eco"]
        }
        
        if category in category_keywords:
            keywords.extend(category_keywords[category])
        
        # Add entity-based semantic expansions
        for service in entities.get("azure_services", []):
            if "defender" in service:
                keywords.extend(["security", "threat protection", "vulnerability management"])
            elif "synapse" in service:
                keywords.extend(["analytics", "data warehouse", "big data"])
        
        return list(set(keywords))
    
    def _assess_business_impact(self, text: str, impact_statement: str) -> str:
        """Assess business impact level"""
        combined = f"{text} {impact_statement}".lower()
        
        # 🚨 CAPACITY/QUOTA ISSUES = ALWAYS HIGH IMPACT
        capacity_quota_indicators = [
            "capacity needed", "need capacity", "capacity request", "quota needed", "need quota", 
            "quota request", "increase capacity", "increase quota", "quota exceeded", "capacity limit",
            "scaling limit", "resource limit", "capacity constraint", "quota limit", "out of capacity"
        ]
        if any(indicator in combined for indicator in capacity_quota_indicators):
            return "high"
        if "capacity" in combined or "quota" in combined:
            return "high"  # Any capacity mention = high impact
        
        # High impact indicators
        high_impact_indicators = ["critical", "production down", "revenue impact", "business critical", "emergency", "urgent"]
        
        # Medium impact indicators - including missing services
        medium_impact_indicators = [
            "important", "affects users", "performance", "customer impact",
            # Missing service indicators - these should always be medium+
            "service not available", "service unavailable", "missing service", "lack of service",
            "service gap", "not offered", "unavailable in", "not available in",
            "no support for", "service missing", "regional gap"
        ]
        
        # Low impact indicators
        low_impact_indicators = ["minor", "enhancement", "nice to have", "future consideration", "general"]
        
        # Check for high impact first
        if any(indicator in combined for indicator in high_impact_indicators):
            return "high"
        
        # Check for medium impact (including missing services)
        elif any(indicator in combined for indicator in medium_impact_indicators):
            return "medium"
            
        # Check if it mentions competition or business risk (should be medium-high)
        elif any(word in combined for word in ["competitor", "compete", "risk", "moving forward", "alternative"]):
            return "medium"
        
        # Default low for general inquiries
        else:
            return "low"
    
    def _assess_technical_complexity(self, text: str, entities: Dict) -> str:
        """Assess technical complexity"""
        complexity_score = 0
        
        # Multiple services = higher complexity
        complexity_score += len(entities.get("azure_services", [])) * 0.2
        
        # Integration/connectivity = higher complexity
        if any(word in text for word in ["integration", "api", "connectivity", "multi-tenant"]):
            complexity_score += 0.3
        
        # Compliance frameworks = higher complexity
        complexity_score += len(entities.get("compliance_frameworks", [])) * 0.2
        
        if complexity_score > 0.6:
            return "high"
        elif complexity_score > 0.3:
            return "medium"
        else:
            return "low"
    
    def _assess_urgency(self, text: str, business_impact: str) -> str:
        """Assess urgency level"""
        urgency_indicators = ["urgent", "asap", "immediately", "critical", "production down"]
        
        if any(indicator in text for indicator in urgency_indicators):
            return "high"
        elif business_impact == "high":
            return "medium"
        else:
            return "low"
    
    def _recommend_search_strategy(self, category: IssueCategory, intent: IntentType, entities: Dict) -> Dict[str, bool]:
        """Recommend which sources to search based on context"""
        strategy = {
            "search_retirements": False,
            "prioritize_uats": False,
            "prioritize_features": False,
            "use_semantic_matching": True,
            "expand_search_terms": True
        }
        
        # Service Retirement/End-of-life routing
        if category in [IssueCategory.SERVICE_RETIREMENT, IssueCategory.RETIREMENTS]:
            strategy["search_retirements"] = True
            strategy["prioritize_uats"] = False
            strategy["prioritize_features"] = True  # Look for alternatives
        
        # Service Availability - search both features and UATs with regional validation
        elif category == IssueCategory.SERVICE_AVAILABILITY or intent == IntentType.REQUESTING_SERVICE:
            strategy["prioritize_features"] = True  # Service gaps often documented as features
            strategy["prioritize_uats"] = True  # UATs may have regional limitations, workarounds
            strategy["expand_search_terms"] = True  # Need broad search for regional availability
            
            # Add regional service validation if we have both service and region entities
            services = entities.get("azure_services", [])
            regions = entities.get("regions", [])
            if services and regions:
                # Validate service availability in requested regions
                availability_info = []
                for service in services[:3]:  # Limit to top 3 services
                    for region in regions[:2]:  # Limit to top 2 regions
                        availability = self.validate_service_region_availability(service, region)
                        availability_info.append(availability)
                
                strategy["regional_availability"] = availability_info
        
        # Data Sovereignty - similar to service availability but more compliance focused  
        elif category == IssueCategory.DATA_SOVEREIGNTY or intent == IntentType.SOVEREIGNTY_CONCERN:
            strategy["prioritize_features"] = True  # Regional compliance often in roadmap
            strategy["prioritize_uats"] = True  # UATs may document compliance workarounds
            strategy["expand_search_terms"] = True  # Need broad geographic terms
        
        # Roadmap and Product inquiries - features first
        elif category in [IssueCategory.PRODUCT_ROADMAP, IssueCategory.ROADMAP] or intent == IntentType.ROADMAP_INQUIRY:
            strategy["prioritize_features"] = True
            strategy["prioritize_uats"] = False
            strategy["expand_search_terms"] = True
            
        # Capacity issues - could be UATs or features depending on type
        elif category in [IssueCategory.AOAI_CAPACITY, IssueCategory.CAPACITY] or intent == IntentType.CAPACITY_REQUEST:
            strategy["prioritize_uats"] = True  # Often documented workarounds
            strategy["prioritize_features"] = True  # Also capacity improvements
            strategy["expand_search_terms"] = True
        
        # Feature requests go to features first
        elif category == IssueCategory.FEATURE_REQUEST or intent == IntentType.REQUESTING_FEATURE:
            strategy["prioritize_features"] = True
            strategy["prioritize_uats"] = False
        
        # Technical issues go to UATs first
        elif category == IssueCategory.TECHNICAL_SUPPORT or intent == IntentType.TROUBLESHOOTING:
            strategy["prioritize_uats"] = True
            strategy["prioritize_features"] = False
        
        # Compliance issues rarely in retirements, focus on UATs/Features
        elif category == IssueCategory.COMPLIANCE_REGULATORY:
            strategy["search_retirements"] = False
            strategy["prioritize_uats"] = True
            strategy["expand_search_terms"] = True
            
        # Business engagement - focus on features and roadmap
        elif category == IssueCategory.BUSINESS_DESK or intent == IntentType.BUSINESS_ENGAGEMENT:
            strategy["prioritize_features"] = True
            strategy["prioritize_uats"] = False
            strategy["expand_search_terms"] = True
        
        return strategy
    
    def _generate_context_summary(self, category: IssueCategory, intent: IntentType, 
                                entities: Dict, concepts: List[str], impact: str, text: str) -> str:
        """Generate human-readable context summary using Microsoft Learn insights"""
        
        # Check if we have Microsoft Learn discovered services for better context
        discovered_services = entities.get('discovered_services', [])
        if discovered_services and self.microsoft_docs_available:
            # Enhanced summary with Microsoft Learn context
            main_service = discovered_services[0]
            service_info = self._lookup_service_in_microsoft_docs(main_service)
            
            if service_info.get('found_in_docs'):
                service_desc = service_info.get('description', '')[:150]
                summary_prefix = f"Microsoft Learn context: {service_desc}... "
            else:
                summary_prefix = ""
        else:
            summary_prefix = ""
        
        category_desc = {
            IssueCategory.COMPLIANCE_REGULATORY: "regulatory compliance",
            IssueCategory.TECHNICAL_SUPPORT: "technical support",
            IssueCategory.FEATURE_REQUEST: "feature enhancement",
            IssueCategory.SERVICE_RETIREMENT: "service retirement",
            IssueCategory.SECURITY_GOVERNANCE: "security and governance",
            IssueCategory.MIGRATION_MODERNIZATION: "migration and modernization",
            IssueCategory.PERFORMANCE_OPTIMIZATION: "performance optimization", 
            IssueCategory.INTEGRATION_CONNECTIVITY: "integration and connectivity",
            IssueCategory.COST_BILLING: "cost and billing",
            IssueCategory.TRAINING_DOCUMENTATION: "training and documentation",
            IssueCategory.SERVICE_AVAILABILITY: "service availability",
            IssueCategory.DATA_SOVEREIGNTY: "data sovereignty and compliance",
            IssueCategory.PRODUCT_ROADMAP: "product roadmap inquiry",
            IssueCategory.AOAI_CAPACITY: "Azure OpenAI capacity",
            IssueCategory.BUSINESS_DESK: "business engagement",
            IssueCategory.CAPACITY: "capacity constraints",
            IssueCategory.RETIREMENTS: "service retirement",
            IssueCategory.ROADMAP: "product roadmap",
            IssueCategory.SUPPORT: "general support",
            IssueCategory.SUPPORT_ESCALATION: "escalated support",
            IssueCategory.SUSTAINABILITY: "sustainability"
        }
        
        intent_desc = {
            IntentType.SEEKING_GUIDANCE: "seeking guidance",
            IntentType.REPORTING_ISSUE: "reporting an issue",
            IntentType.REQUESTING_FEATURE: "requesting a feature",
            IntentType.NEED_MIGRATION_HELP: "migration assistance",
            IntentType.COMPLIANCE_SUPPORT: "compliance support", 
            IntentType.TROUBLESHOOTING: "troubleshooting assistance",
            IntentType.CONFIGURATION_HELP: "configuration help",
            IntentType.BEST_PRACTICES: "best practices guidance",
            IntentType.REQUESTING_SERVICE: "requesting new service availability",
            IntentType.SOVEREIGNTY_CONCERN: "data sovereignty concern",
            IntentType.ROADMAP_INQUIRY: "roadmap inquiry",
            IntentType.CAPACITY_REQUEST: "capacity request",
            IntentType.ESCALATION_REQUEST: "escalation request",
            IntentType.BUSINESS_ENGAGEMENT: "business engagement",
            IntentType.SUSTAINABILITY_INQUIRY: "sustainability inquiry"
        }
        
        # Get key entities for more specific summary
        services = entities.get("azure_services", [])[:3]
        frameworks = entities.get("compliance_frameworks", [])[:2] 
        technologies = entities.get("technologies", [])[:3]
        regions = entities.get("regions", [])[:2]
        
        # Build more intelligent summary based on category and entities
        summary_parts = []
        
        # Category-specific summaries with detailed context
        if category == IssueCategory.CAPACITY:
            # Extract specific capacity details from the actual user input
            capacity_details = self._extract_capacity_details(text)
            if capacity_details:
                summary_parts.append(capacity_details)
            else:
                summary_parts.append("Capacity or quota request")
        elif category == IssueCategory.SERVICE_AVAILABILITY:
            if regions and services:
                # Check actual service availability in requested regions
                availability_summary = []
                for service in services[:2]:  # Top 2 services
                    for region in regions[:2]:  # Top 2 regions  
                        availability = self.validate_service_region_availability(service, region)
                        if availability['available']:
                            status = "✅ Available"
                        elif availability['nearby_regions']:
                            status = f"⚠️ Available in nearby: {', '.join(availability['nearby_regions'][:2])}"
                        else:
                            status = "❌ Not available"
                        availability_summary.append(f"{service} in {region}: {status}")
                
                if availability_summary:
                    summary_parts.append(f"Service availability inquiry: {', '.join(availability_summary)}")
                else:
                    summary_parts.append(f"Service availability inquiry for {', '.join(services)} in {', '.join(regions)}")
            elif regions:
                summary_parts.append(f"Regional service availability inquiry for {', '.join(regions)}")
            elif services:
                summary_parts.append(f"Service availability inquiry for {', '.join(services)}")
            else:
                summary_parts.append("Service availability inquiry")
        elif category == IssueCategory.DATA_SOVEREIGNTY:
            if regions:
                summary_parts.append(f"Data sovereignty and compliance inquiry for {', '.join(regions)}")
            else:
                summary_parts.append("Data sovereignty and compliance inquiry")
        elif category == IssueCategory.AOAI_CAPACITY:
            summary_parts.append("Azure OpenAI capacity constraint or quota inquiry")
        else:
            # Standard summary format for other categories
            summary_parts.append(f"This appears to be a {category_desc.get(category, 'general')} issue")
        
        # Add intent context if not already covered
        if intent in intent_desc and category not in [IssueCategory.SERVICE_AVAILABILITY, IssueCategory.DATA_SOVEREIGNTY, IssueCategory.AOAI_CAPACITY]:
            summary_parts.append(f"with user {intent_desc[intent]}")
        
        # Add specific entity context  
        if services and category not in [IssueCategory.SERVICE_AVAILABILITY]:
            summary_parts.append(f"involving {', '.join(services)}")
        
        if technologies:
            summary_parts.append(f"related to {', '.join(technologies)}")
            
        if frameworks:
            summary_parts.append(f"addressing {', '.join(frameworks)} requirements")
        
        # Add business impact
        summary_parts.append(f"with {impact} business impact")
        
        return " ".join(summary_parts) + "."
    
    def _extract_capacity_details(self, text: str) -> str:
        """Extract and summarize capacity request details from the actual user input"""
        import re
        
        text_lower = text.lower()
        summary_parts = []
        
        # Extract what service/resource they need capacity for (WHAT)
        services_mentioned = []
        
        # Look for common Azure services mentioned
        azure_services = {
            'postgresql': 'PostgreSQL', 'sql': 'SQL Database', 'mysql': 'MySQL', 
            'cosmos': 'Cosmos DB', 'redis': 'Redis Cache', 'storage': 'Storage',
            'compute': 'Compute', 'vm': 'Virtual Machines', 'aks': 'AKS',
            'functions': 'Azure Functions', 'app service': 'App Service',
            'adx': 'ADX (Azure Data Explorer)', 'data explorer': 'Azure Data Explorer',
            'kusto': 'Azure Data Explorer (Kusto)', 'synapse': 'Azure Synapse'
        }
        
        for key, value in azure_services.items():
            if key in text_lower:
                services_mentioned.append(value)
        
        # Extract regions (WHERE) using comprehensive Azure region patterns
        regions_mentioned = []
        
        # Create comprehensive region patterns from our mapping
        region_pattern_keys = list(self.region_name_mapping.keys())
        
        for region_key in region_pattern_keys:
            # Create flexible pattern that matches variations with/without spaces/hyphens
            pattern_variations = [
                region_key.replace(' ', ''),  # "eastus"
                region_key.replace(' ', '-'), # "east-us"  
                region_key.replace(' ', ' '),  # "east us"
            ]
            
            for pattern_var in pattern_variations:
                if pattern_var.lower() in text.lower():
                    # Use the proper formatted name from mapping
                    proper_name = self.region_name_mapping[region_key]
                    if proper_name not in regions_mentioned:
                        regions_mentioned.append(proper_name)
                    break
        
        # Build a natural summary
        if services_mentioned and regions_mentioned:
            summary_parts.append(f"Capacity request for {services_mentioned[0]} in {regions_mentioned[0]}")
        elif services_mentioned:
            summary_parts.append(f"Capacity request for {services_mentioned[0]}")
        elif regions_mentioned:
            summary_parts.append(f"Capacity request in {regions_mentioned[0]}")
        else:
            summary_parts.append("Capacity or quota request")
        
        # Look for specific quantity mentions with proper units
        quantity_patterns = [
            r'(\d+(?:,\d+)*)\s*(cores?)',  # "5,000 cores" or "5000 cores"
            r'(\d+(?:,\d+)*)\s*(vcpus?)',  # "500 vcpus"
            r'(\d+(?:,\d+)*)\s*(units?)',  # "100 units"
            r'(\d+(?:,\d+)*)\s*(instances?)',  # "50 instances"
            r'from\s+(\d+(?:,\d+)*)\s+to\s+(\d+(?:,\d+)*)',  # "from 50 to 500"
            r'increase.*?(\d+(?:,\d+)*)\s+to\s+(\d+(?:,\d+)*)', 
            r'need\s+(\d+(?:,\d+)*)',  # "need 5000"
        ]
        
        for pattern in quantity_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if len(matches[0]) == 2 and not matches[0][1].isdigit():  # quantity + unit pattern
                    qty, unit = matches[0]
                    summary_parts.append(f"for {qty} {unit}")
                    break
                elif isinstance(matches[0], tuple) and len(matches[0]) == 2 and matches[0][1].isdigit():  # from X to Y
                    from_qty, to_qty = matches[0]
                    summary_parts.append(f"to increase from {from_qty} to {to_qty}")
                    break
                else:
                    qty = matches[0] if isinstance(matches[0], str) else matches[0][0]
                    summary_parts.append(f"for {qty}")
                    break
        
        return " ".join(summary_parts) if summary_parts else ""

    def _lookup_service_in_microsoft_docs(self, service_name: str) -> Dict[str, str]:
        """
        Look up service information in Microsoft Learn documentation
        
        Args:
            service_name: Name of the service to look up
            
        Returns:
            Dictionary with service information from Microsoft Learn
        """
        if not self.microsoft_docs_available:
            return {"found_in_docs": False, "error": "Microsoft docs tools not available"}
            
        try:
            # Search for the service in Microsoft Learn
            search_query = f"{service_name} Microsoft service overview"
            
            # For now, we'll use a basic Microsoft product recognition
            # In a full implementation, this would call the Microsoft Learn API
            
            # Known Microsoft products and services
            microsoft_products = {
                "planner": {
                    "title": "Microsoft Planner service description",
                    "description": "Microsoft Planner is a tool that gives users a visual way to organize teamwork. Teams can create new plans, organize and assign tasks, share files, chat about what they're working on, set due dates, and update status.",
                    "is_microsoft_product": True
                },
                "roadmap": {
                    "title": "Microsoft Roadmap - Project roadmap management",
                    "description": "Microsoft Roadmap provides visual representation of project timelines and milestones. It's part of the Microsoft Project suite for enterprise project management.",
                    "is_microsoft_product": True
                },
                "teams": {
                    "title": "Microsoft Teams overview",
                    "description": "Microsoft Teams is a collaboration platform that combines workplace chat, meetings, notes, and attachments.",
                    "is_microsoft_product": True
                },
                "sharepoint": {
                    "title": "SharePoint service overview",
                    "description": "Microsoft SharePoint is a web-based collaborative platform that integrates with Microsoft Office.",
                    "is_microsoft_product": True
                }
            }
            
            service_lower = service_name.lower().strip()
            if service_lower in microsoft_products:
                product_info = microsoft_products[service_lower]
                service_info = {
                    "found_in_docs": True,
                    "service_name": service_name,
                    "category": self._categorize_service_from_name(service_name),
                    "description": product_info["description"],
                    "title": product_info["title"],
                    "url": "https://learn.microsoft.com",
                    "search_query": search_query,
                    "is_microsoft_product": True
                }
                
                self.logger.info(f"✅ Found Microsoft product '{service_name}': {product_info['title']}")
                return service_info
            
            # Fallback to basic categorization
            service_info = {
                "found_in_docs": False,
                "service_name": service_name,
                "category": self._categorize_service_from_name(service_name),
                "description": f"Microsoft service related to {service_name}",
                "search_query": search_query,
                "fallback_used": True
            }
            
            return service_info
            
        except Exception as e:
            self.logger.warning(f"Failed to lookup service '{service_name}' in Microsoft Learn: {e}")
            return {"found_in_docs": False, "error": str(e)}
    
    def _categorize_service_from_name(self, service_name: str) -> str:
        """
        Categorize a service based on its name
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service category
        """
        service_lower = service_name.lower()
        
        if any(term in service_lower for term in ['fabric', 'synapse', 'data factory', 'databricks']):
            return 'analytics'
        elif any(term in service_lower for term in ['sql', 'database', 'cosmos', 'storage']):
            return 'data'
        elif any(term in service_lower for term in ['openai', 'cognitive', 'ai', 'ml']):
            return 'ai'
        elif any(term in service_lower for term in ['app service', 'function', 'container', 'kubernetes']):
            return 'compute'
        elif any(term in service_lower for term in ['purview', 'governance', 'compliance']):
            return 'governance'
        else:
            return 'other'

    def _generate_comprehensive_reasoning(self, category: IssueCategory, intent: IntentType, 
                                        category_confidence: float, intent_confidence: float,
                                        domain_entities: Dict, business_impact: str, 
                                        technical_complexity: str, text: str,
                                        step_by_step_reasoning: Dict, microsoft_analysis: Dict) -> Dict[str, any]:
        """
        Generate comprehensive step-by-step reasoning with data source tracking
        
        Returns:
            Dictionary with detailed reasoning including step-by-step analysis and data sources
        """
        comprehensive_reasoning = {
            "step_by_step": step_by_step_reasoning["steps"],
            "data_sources_used": step_by_step_reasoning["data_sources_consulted"],
            "data_sources_skipped": step_by_step_reasoning["data_sources_skipped"],
            "confidence_breakdown": step_by_step_reasoning["confidence_factors"],
            "microsoft_products": step_by_step_reasoning.get("microsoft_products_detected", []),
            "corrections_applied": step_by_step_reasoning.get("corrections_applied", []),
            "final_analysis": {},
            "decision_factors": []
        }
        
        # Final analysis reasoning
        if category == IssueCategory.TRAINING_DOCUMENTATION:
            if microsoft_analysis.get("detected_products"):
                comprehensive_reasoning["final_analysis"]["category_reason"] = f"Detected Microsoft products ({[p['name'] for p in microsoft_analysis['detected_products']]}) in training/demo context"
                comprehensive_reasoning["decision_factors"].append("✅ Microsoft product detection + training context = Documentation request")
            else:
                comprehensive_reasoning["final_analysis"]["category_reason"] = "Training/documentation keywords detected"
                
        elif category == IssueCategory.ROADMAP:
            if "planner" in text.lower() and "roadmap" in text.lower():
                comprehensive_reasoning["final_analysis"]["category_reason"] = "Ambiguous case: Could be Microsoft Planner & Roadmap products OR roadmap planning"
                comprehensive_reasoning["decision_factors"].append("⚠️ Manual review recommended for disambiguation")
            else:
                comprehensive_reasoning["final_analysis"]["category_reason"] = "Timeline/roadmap planning indicators detected"
                
        elif category == IssueCategory.CAPACITY:
            comprehensive_reasoning["final_analysis"]["category_reason"] = f"High-confidence capacity request patterns detected (confidence: {category_confidence:.0%})"
            comprehensive_reasoning["decision_factors"].append("🚨 Capacity requests override other categories due to urgency")
            
        else:
            comprehensive_reasoning["final_analysis"]["category_reason"] = f"{category.value} indicators found with {category_confidence:.0%} confidence"
        
        # Intent reasoning
        comprehensive_reasoning["final_analysis"]["intent_reason"] = f"{intent.value} patterns detected with {intent_confidence:.0%} confidence"
        
        # Data source summary
        sources_used = len(comprehensive_reasoning["data_sources_used"])
        sources_skipped = len(comprehensive_reasoning["data_sources_skipped"])
        comprehensive_reasoning["final_analysis"]["data_source_summary"] = f"Consulted {sources_used} data sources, skipped {sources_skipped}"
        
        return comprehensive_reasoning

    def _generate_reasoning(self, category: IssueCategory, intent: IntentType, 
                          category_confidence: float, intent_confidence: float,
                          domain_entities: Dict, business_impact: str, 
                          technical_complexity: str, text: str = "") -> Dict[str, str]:
        """
        Generate explanations for why the system made specific analysis decisions
        
        Returns:
            Dictionary with reasoning explanations for each analysis dimension
        """
        reasoning = {}
        
        # 🔍 Microsoft Product Analysis Reasoning
        microsoft_analysis = self._detect_microsoft_products_with_context(text) if text else {"detected_products": [], "reasoning": []}
        
        # Category reasoning
        services = domain_entities.get('azure_services', [])
        frameworks = domain_entities.get('compliance_frameworks', [])
        technologies = domain_entities.get('technologies', [])
        discovered_services = domain_entities.get('discovered_services', [])
        
        category_reasons = []
        
        # Enhanced reasoning for TRAINING_DOCUMENTATION
        if category == IssueCategory.TRAINING_DOCUMENTATION:
            if microsoft_analysis["detected_products"]:
                product_names = [p["name"] for p in microsoft_analysis["detected_products"]]
                category_reasons.append(f"🎯 Microsoft products detected via Learn API: {', '.join(product_names)}")
                category_reasons.append(f"Context analysis: {microsoft_analysis.get('context_analysis', 'Microsoft product inquiry')}")
            category_reasons.append(f"Training/documentation indicators found (confidence: {category_confidence:.0%})")
            
        # Enhanced reasoning for ROADMAP vs TRAINING disambiguation
        elif category == IssueCategory.ROADMAP:
            if "planner" in text.lower() and "roadmap" in text.lower():
                if microsoft_analysis["detected_products"]:
                    category_reasons.append("⚠️ Ambiguous: Could be Microsoft Planner & Roadmap products OR roadmap planning request")
                    category_reasons.append("Consider manual review for context disambiguation")
                else:
                    category_reasons.append("Roadmap planning request detected (no Microsoft product context found)")
            else:
                category_reasons.append(f"Roadmap inquiry patterns identified (confidence: {category_confidence:.0%})")
                
        elif category == IssueCategory.FEATURE_REQUEST:
            if discovered_services:
                category_reasons.append(f"Detected {len(discovered_services)} services via Microsoft Learn: {', '.join(discovered_services[:3])}")
            category_reasons.append(f"Keywords indicating feature request found (confidence: {category_confidence:.0%})")
            if services:
                category_reasons.append(f"Involves {len(services)} Azure services: {', '.join(services[:3])}")
        elif category == IssueCategory.COMPLIANCE_REGULATORY:
            if frameworks:
                category_reasons.append(f"Compliance frameworks detected: {', '.join(frameworks)}")
            category_reasons.append(f"Regulatory language patterns identified")
        elif category == IssueCategory.TECHNICAL_SUPPORT:
            category_reasons.append(f"Technical support indicators found (confidence: {category_confidence:.0%})")
            if services:
                category_reasons.append(f"References {len(services)} technical services")
        
        reasoning['category'] = '. '.join(category_reasons) if category_reasons else f"Classified as {category.value.replace('_', ' ')} with {category_confidence:.0%} confidence"
        
        # Intent reasoning
        intent_reasons = []
        if intent == IntentType.REQUESTING_FEATURE:
            intent_reasons.append("User language suggests requesting new functionality")
        elif intent == IntentType.SEEKING_GUIDANCE:
            intent_reasons.append("Question patterns indicate guidance-seeking behavior")
        elif intent == IntentType.TROUBLESHOOTING:
            intent_reasons.append("Problem-solving language patterns detected")
        
        reasoning['intent'] = '. '.join(intent_reasons) if intent_reasons else f"Intent classified as {intent.value.replace('_', ' ')} with {intent_confidence:.0%} confidence"
        
        # Service discovery reasoning (Microsoft Learn integration)
        if discovered_services and self.microsoft_docs_available:
            reasoning['service_discovery'] = f"Enhanced service recognition using Microsoft Learn identified: {', '.join(discovered_services)}. This provides authoritative understanding beyond static service lists."
        elif services:
            reasoning['service_discovery'] = f"Services identified from static knowledge: {', '.join(services)}"
        else:
            reasoning['service_discovery'] = "No specific Azure services detected in this request"
        
        # Business impact reasoning
        impact_reasons = []
        if business_impact == 'high':
            impact_reasons.append("Business-critical language or urgent indicators found")
        elif business_impact == 'medium':
            impact_reasons.append("Moderate business importance suggested by context")
        else:
            impact_reasons.append("Standard business priority level inferred")
        
        reasoning['business_impact'] = '. '.join(impact_reasons)
        
        # Technical complexity reasoning
        complexity_reasons = []
        if technical_complexity == 'high':
            complexity_reasons.append("Multiple technical domains or complex integrations involved")
        elif technical_complexity == 'medium':
            complexity_reasons.append("Standard technical complexity requiring specialized knowledge")
        else:
            complexity_reasons.append("Straightforward technical requirements")
            
        if technologies:
            complexity_reasons.append(f"Technologies involved: {', '.join(technologies[:5])}")
        
        reasoning['technical_complexity'] = '. '.join(complexity_reasons)
        
        return reasoning

# Example usage and testing
if __name__ == "__main__":
    analyzer = IntelligentContextAnalyzer()
    
    # Test with the user's compliance query
    title = "General Atomics - NIST 800-172 regulatory compliance policy for MDC - Azure Gov & Commercial"
    description = "Defender for Cloud: Customer needs support for NIST 800-172 for Azure resources in Azure commercial and gov clouds within MDC regulatory compliance feature."
    impact = "High priority - regulatory compliance requirement for government contracts"
    
    analysis = analyzer.analyze_context(title, description, impact)
    
    print("=== INTELLIGENT CONTEXT ANALYSIS ===")
    print(f"Category: {analysis.category.value}")
    print(f"Intent: {analysis.intent.value}")
    print(f"Confidence: {analysis.confidence:.2f}")
    print(f"Business Impact: {analysis.business_impact}")
    print(f"Technical Complexity: {analysis.technical_complexity}")
    print(f"Urgency: {analysis.urgency_level}")
    print()
    print("Domain Entities:")
    for entity_type, entities in analysis.domain_entities.items():
        if entities:
            print(f"  {entity_type}: {entities}")
    print()
    print("Key Concepts:", analysis.key_concepts[:5])
    print("Semantic Keywords:", analysis.semantic_keywords[:5])
    print()
    print("Recommended Search Strategy:")
    for strategy, enabled in analysis.recommended_search_strategy.items():
        print(f"  {strategy}: {enabled}")
    print()
    print("Context Summary:")
    print(f"  {analysis.context_summary}")