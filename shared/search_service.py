"""
Resource Search Service
=======================

Orchestrates comprehensive searches for user issues across multiple data sources:
1. Microsoft Learn documentation
2. Similar/alternative Azure products
3. Regional service availability
4. Capacity guidance (AOAI and standard Azure)
5. Retirement information and guidance

This service provides actionable resources to help users resolve issues before
creating support tickets.
"""

from typing import Dict, List, Optional, Any
import json
from pathlib import Path
import requests
from dataclasses import dataclass
import re


@dataclass
class SearchResult:
    """Individual search result with title, URL, and snippet"""
    title: str
    url: str
    snippet: str
    source: str  # "learn", "product", "region", "capacity", "retirement"
    relevance_score: float = 0.0
    

@dataclass
class ComprehensiveSearchResults:
    """Complete search results across all sources"""
    learn_docs: List[SearchResult]
    similar_products: List[Dict[str, str]]
    regional_options: List[Dict[str, Any]]
    capacity_guidance: Optional[Dict[str, str]]
    retirement_info: Optional[Dict[str, Any]]
    search_metadata: Dict[str, Any]


class ResourceSearchService:
    """
    Comprehensive resource search for Azure issues
    
    Searches across multiple sources to provide users with relevant
    documentation, alternatives, and guidance before creating tickets.
    """
    
    def __init__(self, use_deep_search: bool = False):
        """
        Initialize search service
        
        Args:
            use_deep_search: If True, performs more extensive searches (slower but more thorough)
        """
        self.use_deep_search = use_deep_search
        self.retirements_data = self._load_retirements()
        
        # Microsoft Learn search via MCP tools (will be called from app.py context)
        self.microsoft_docs_available = True
        
    def _load_retirements(self) -> Dict:
        """Load retirement data from JSON file"""
        retirements_file = Path(__file__).parent.parent / "data" / "retirements.json"
        if retirements_file.exists():
            with open(retirements_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def search_all(
        self,
        title: str,
        description: str,
        category: str,
        intent: str,
        domain_entities: Dict[str, List[str]]
    ) -> ComprehensiveSearchResults:
        """
        Perform comprehensive search across all sources
        
        Args:
            title: Issue title
            description: Issue description
            category: Classified category (e.g., "capacity_request")
            intent: Classified intent (e.g., "capacity_increase")
            domain_entities: Extracted entities (services, regions, etc.)
            
        Returns:
            ComprehensiveSearchResults with findings from all sources
        """
        results = ComprehensiveSearchResults(
            learn_docs=[],
            similar_products=[],
            regional_options=[],
            capacity_guidance=None,
            retirement_info=None,
            search_metadata={
                "deep_search": self.use_deep_search,
                "searches_performed": []
            }
        )
        
        # 1. Search Microsoft Learn (will be populated by caller using MCP tools)
        # This is a placeholder - actual search done via MCP in app.py
        results.search_metadata["searches_performed"].append("microsoft_learn")
        
        # 2. Find similar/alternative products
        if domain_entities.get('azure_services'):
            results.similar_products = self._find_similar_products(
                domain_entities['azure_services'],
                category,
                intent
            )
            results.search_metadata["searches_performed"].append("similar_products")
        
        # 3. Check regional availability
        if category in ['service_issue', 'regional_issue'] or domain_entities.get('regions'):
            results.regional_options = self._check_regional_availability(
                domain_entities.get('azure_services', []),
                domain_entities.get('regions', [])
            )
            results.search_metadata["searches_performed"].append("regional_availability")
        
        # 4. Provide capacity guidance if capacity request
        if category == 'capacity_request' or 'capacity' in intent.lower():
            results.capacity_guidance = self._get_capacity_guidance(
                domain_entities.get('azure_services', []),
                title,
                description
            )
            results.search_metadata["searches_performed"].append("capacity_guidance")
        
        # 5. Check for retirement information
        retirement_keywords = ['retir', 'deprecat', 'end of life', 'eol', 'sunset']
        text_to_check = f"{title} {description}".lower()
        if any(keyword in text_to_check for keyword in retirement_keywords):
            results.retirement_info = self._check_retirement_info(
                domain_entities.get('azure_services', []),
                title,
                description
            )
            results.search_metadata["searches_performed"].append("retirement_info")
        
        return results
    
    def _find_similar_products(
        self,
        services: List[str],
        category: str,
        intent: str
    ) -> List[Dict[str, str]]:
        """
        Find similar or alternative Azure products
        
        Args:
            services: List of Azure services mentioned
            category: Issue category
            intent: User intent
            
        Returns:
            List of alternative products with descriptions
        """
        alternatives = []
        
        # Common Azure service alternatives
        alternatives_map = {
            # Compute
            'virtual machines': [
                {'name': 'Azure Container Instances', 'reason': 'Simpler container deployment without VMs', 'url': 'https://learn.microsoft.com/azure/container-instances/'},
                {'name': 'Azure App Service', 'reason': 'Managed web app hosting', 'url': 'https://learn.microsoft.com/azure/app-service/'},
                {'name': 'Azure Kubernetes Service', 'reason': 'Orchestrated container platform', 'url': 'https://learn.microsoft.com/azure/aks/'}
            ],
            'app service': [
                {'name': 'Azure Container Apps', 'reason': 'Serverless container platform', 'url': 'https://learn.microsoft.com/azure/container-apps/'},
                {'name': 'Azure Functions', 'reason': 'Event-driven serverless compute', 'url': 'https://learn.microsoft.com/azure/azure-functions/'},
                {'name': 'Azure Static Web Apps', 'reason': 'Optimized for static content and APIs', 'url': 'https://learn.microsoft.com/azure/static-web-apps/'}
            ],
            
            # Databases
            'sql database': [
                {'name': 'Azure SQL Managed Instance', 'reason': 'Full SQL Server compatibility', 'url': 'https://learn.microsoft.com/azure/azure-sql/managed-instance/'},
                {'name': 'Azure Cosmos DB', 'reason': 'Globally distributed NoSQL database', 'url': 'https://learn.microsoft.com/azure/cosmos-db/'},
                {'name': 'Azure Database for PostgreSQL', 'reason': 'Managed PostgreSQL service', 'url': 'https://learn.microsoft.com/azure/postgresql/'}
            ],
            'cosmos db': [
                {'name': 'Azure SQL Database', 'reason': 'Relational database service', 'url': 'https://learn.microsoft.com/azure/azure-sql/database/'},
                {'name': 'Azure Table Storage', 'reason': 'Simple NoSQL key-value storage', 'url': 'https://learn.microsoft.com/azure/storage/tables/'},
                {'name': 'Azure Cache for Redis', 'reason': 'In-memory data store', 'url': 'https://learn.microsoft.com/azure/azure-cache-for-redis/'}
            ],
            
            # AI/ML
            'azure openai': [
                {'name': 'Azure AI Services', 'reason': 'Pre-built AI capabilities (vision, speech, language)', 'url': 'https://learn.microsoft.com/azure/ai-services/'},
                {'name': 'Azure Machine Learning', 'reason': 'Build and deploy custom ML models', 'url': 'https://learn.microsoft.com/azure/machine-learning/'},
                {'name': 'Azure Cognitive Search', 'reason': 'AI-powered search with semantic ranking', 'url': 'https://learn.microsoft.com/azure/search/'}
            ],
            
            # Storage
            'blob storage': [
                {'name': 'Azure Data Lake Storage', 'reason': 'Optimized for big data analytics', 'url': 'https://learn.microsoft.com/azure/storage/blobs/data-lake-storage-introduction'},
                {'name': 'Azure Files', 'reason': 'Fully managed file shares', 'url': 'https://learn.microsoft.com/azure/storage/files/'},
                {'name': 'Azure NetApp Files', 'reason': 'Enterprise-grade file storage', 'url': 'https://learn.microsoft.com/azure/azure-netapp-files/'}
            ]
        }
        
        # Match services to alternatives
        for service in services:
            service_lower = service.lower()
            for key, alts in alternatives_map.items():
                if key in service_lower or service_lower in key:
                    for alt in alts:
                        # Avoid suggesting the same service
                        if alt['name'].lower() not in service_lower:
                            alternatives.append({
                                'original_service': service,
                                'alternative_name': alt['name'],
                                'reason': alt['reason'],
                                'learn_url': alt['url']
                            })
        
        # Remove duplicates
        seen = set()
        unique_alternatives = []
        for alt in alternatives:
            key = alt['alternative_name']
            if key not in seen:
                seen.add(key)
                unique_alternatives.append(alt)
        
        return unique_alternatives[:5] if not self.use_deep_search else unique_alternatives
    
    def _check_regional_availability(
        self,
        services: List[str],
        current_regions: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Check which regions offer the requested services
        
        Args:
            services: List of Azure services
            current_regions: Regions mentioned in issue
            
        Returns:
            List of regions with service availability
        """
        regional_options = []
        
        # Common Azure regions and their characteristics
        regions_info = {
            'East US': {'paired': 'West US', 'availability_zones': True, 'features': ['Low latency for East Coast US']},
            'West US': {'paired': 'East US', 'availability_zones': True, 'features': ['Low latency for West Coast US']},
            'North Central US': {'paired': 'South Central US', 'availability_zones': True, 'features': ['Central US location']},
            'West Europe': {'paired': 'North Europe', 'availability_zones': True, 'features': ['GDPR compliant', 'EU data residency']},
            'East Asia': {'paired': 'Southeast Asia', 'availability_zones': True, 'features': ['Low latency for Asia Pacific']},
            'UK South': {'paired': 'UK West', 'availability_zones': True, 'features': ['UK data residency']},
            'Canada Central': {'paired': 'Canada East', 'availability_zones': True, 'features': ['Canadian data residency']},
            'Australia East': {'paired': 'Australia Southeast', 'availability_zones': True, 'features': ['Australian data residency']}
        }
        
        # If user is having issues with a specific region, suggest alternatives
        if current_regions:
            for region in current_regions:
                region_data = regions_info.get(region, {})
                if region_data:
                    # Suggest paired region
                    paired = region_data.get('paired')
                    if paired:
                        regional_options.append({
                            'region': paired,
                            'reason': f'Paired region with {region} for disaster recovery',
                            'features': regions_info.get(paired, {}).get('features', []),
                            'learn_url': 'https://learn.microsoft.com/azure/reliability/cross-region-replication-azure'
                        })
        
        # Add general regional guidance
        if services and not regional_options:
            regional_options.append({
                'region': 'Multiple regions available',
                'reason': 'Check Azure Products by Region for service availability',
                'features': ['Global distribution', 'High availability'],
                'learn_url': 'https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/',
                'reference_url': 'https://learn.microsoft.com/azure/reliability/availability-zones-overview'
            })
        
        return regional_options[:3] if not self.use_deep_search else regional_options
    
    def _get_capacity_guidance(
        self,
        services: List[str],
        title: str,
        description: str
    ) -> Optional[Dict[str, str]]:
        """
        Provide capacity increase guidance
        
        Args:
            services: Azure services mentioned
            title: Issue title
            description: Issue description
            
        Returns:
            Capacity guidance with relevant links
        """
        # Check if this is Azure OpenAI capacity request
        text_combined = f"{title} {description}".lower()
        is_aoai = any(keyword in text_combined for keyword in ['openai', 'gpt', 'chatgpt', 'azure ai'])
        
        if is_aoai:
            return {
                'type': 'Azure OpenAI Capacity',
                'title': 'Azure OpenAI Service Capacity Guidance',
                'description': 'For Azure OpenAI capacity increases, quotas, and provisioned throughput requests',
                'primary_url': 'https://aka.ms/aicapacityhub',
                'additional_resources': [
                    {
                        'title': 'Understanding Azure OpenAI Quotas',
                        'url': 'https://learn.microsoft.com/azure/ai-services/openai/quotas-limits'
                    },
                    {
                        'title': 'Provisioned Throughput Units',
                        'url': 'https://learn.microsoft.com/azure/ai-services/openai/concepts/provisioned-throughput'
                    }
                ]
            }
        else:
            return {
                'type': 'Standard Azure Capacity',
                'title': 'Azure Capacity Request Guidance',
                'description': 'For standard Azure resource capacity increases and quota adjustments',
                'primary_url': 'https://aka.ms/AzureCapacity',
                'additional_resources': [
                    {
                        'title': 'Azure Subscription Limits and Quotas',
                        'url': 'https://learn.microsoft.com/azure/azure-resource-manager/management/azure-subscription-service-limits'
                    },
                    {
                        'title': 'Request Quota Increases',
                        'url': 'https://learn.microsoft.com/azure/quotas/quickstart-increase-quota-portal'
                    }
                ]
            }
    
    def _check_retirement_info(
        self,
        services: List[str],
        title: str,
        description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check for service retirement information from multiple sources
        
        SEARCH STRATEGY (in order):
        1. Local retirements.json database (90+ entries)
        2. Extract service names from text if services list empty
        3. Microsoft Learn online search (fallback if no local results)
        4. Azure Updates API (future enhancement)
        
        FILTERING APPROACH:
        - Word boundary regex matching (not substring)
        - Service name normalization (lowercase, strip whitespace)
        - Partial matching for service variations (e.g., "Defender" vs "Microsoft Defender XDR")
        
        Args:
            services: Azure services from domain entity extraction
            title: Issue title containing potential service names
            description: Full issue description with context
            
        Returns:
            Retirement information dict with:
            - found: Boolean indicating if retirements detected
            - count: Number of relevant retirements
            - retirements: List of retirement details (service, date, URLs, replacements)
            - general_guidance_url: Microsoft Learn migration guidance
        """
        text_combined = f"{title} {description}".lower()
        
        retirement_results = []
        
        # STEP 1: Extract service names if services list is empty
        # This happens when domain entity extraction doesn't capture services
        # Uses pattern matching: "X is retiring", "retirement of X", "X end of life"
        if not services:
            # Try to extract service names from text by checking against known retirement services
            import re
            potential_services = []
            if self.retirements_data:
                for retirement in self.retirements_data.get('retirements', []):
                    service_name = retirement.get('service_name', '').lower().strip()
                    if service_name:
                        # Use word boundary matching to avoid false positives
                        # e.g., "service" won't match "services"
                        pattern = r'\b' + re.escape(service_name) + r'\b'
                        if re.search(pattern, text_combined):
                            potential_services.append(service_name)
            services = potential_services
        
        normalized_services = [s.lower().strip() for s in services] if services else []
        
        print(f"[RetirementCheck] Detected services: {normalized_services}")
        print(f"[RetirementCheck] Issue text contains: {text_combined[:100]}...")
        
        # STEP 2: Search local retirements.json database
        
        # STEP 2: Search local retirements.json database
        if self.retirements_data:
            for retirement in self.retirements_data.get('retirements', []):
                service_name = retirement.get('service_name', '').lower().strip()
                feature_name = retirement.get('feature_name', '').lower().strip()
                
                # MATCHING CRITERIA (must meet at least one):
                # 1. Full service name mentioned in text (word boundary matching)
                #    Example: "Microsoft Defender XDR" matches in "XDR to retire"
                # 2. Service name matches detected services (partial match for variations)
                #    Example: "Defender" matches "Microsoft Defender XDR"
                # 3. Feature name mentioned in text (word boundary)
                #    Example: "Deception Capability" in title/description
                
                import re
                # Use word boundaries to avoid partial matches like "service" matching "services"
                service_pattern = r'\b' + re.escape(service_name) + r'\b'
                feature_pattern = r'\b' + re.escape(feature_name) + r'\b' if feature_name else None
                
                # Check if mentioned directly in issue text
                is_mentioned = (
                    (service_name and re.search(service_pattern, text_combined)) or
                    (feature_name and feature_pattern and re.search(feature_pattern, text_combined))
                )
                
                # Check if matches detected services (allows partial matches)
                # This catches variations like "Defender" vs "Microsoft Defender XDR"
                is_detected_service = any(
                    (ns and service_name and (ns in service_name or service_name in ns))
                    for ns in normalized_services
                )
                
                if is_mentioned or is_detected_service:
                    print(f"[RetirementCheck] MATCH: {service_name} / {feature_name}")
                    print(f"[RetirementCheck]   - mentioned: {is_mentioned}, detected: {is_detected_service}")
                    retirement_results.append({
                        'service': retirement.get('service_name'),
                        'feature': retirement.get('feature_name'),
                        'retirement_date': retirement.get('retirement_date'),
                        'announcement_url': retirement.get('announcement_url'),
                        'migration_guide': retirement.get('migration_guide_url'),
                        'extension_available': retirement.get('extension_available', False),
                        'extension_url': retirement.get('extension_request_url'),
                        'replacement': retirement.get('replacement_service')
                    })
        
        print(f"[RetirementCheck] Found {len(retirement_results)} retirements from retirements.json")
        
        # STEP 3: If no results from local JSON, search online sources
        # This provides comprehensive coverage even for new/unlisted retirements
        if not retirement_results:
            print(f"[RetirementCheck] No JSON results, searching Microsoft Learn and Azure Updates...")
            online_retirements = self._search_online_retirements(title, description, services)
            if online_retirements:
                retirement_results.extend(online_retirements)
                print(f"[RetirementCheck] Found {len(online_retirements)} retirements from online sources")
        
        # STEP 4: Return results or guidance
        if retirement_results:
            return {
                'found': True,
                'count': len(retirement_results),
                'retirements': retirement_results,
                'general_guidance_url': 'https://learn.microsoft.com/azure/advisor/advisor-how-to-plan-migration-workloads-service-retirement'
            }
        
        # Even if no specific retirement found, provide general guidance
        return {
            'found': False,
            'message': 'No specific retirement information found in our database or online sources',
            'general_guidance_url': 'https://learn.microsoft.com/azure/advisor/advisor-how-to-plan-migration-workloads-service-retirement'
        }
    
    def _search_online_retirements(
        self,
        title: str,
        description: str,
        services: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Search online sources for retirement information when local database is empty
        
        ONLINE SOURCES (in order):
        1. Microsoft Learn documentation search
        2. Azure Updates RSS feed (future)
        3. Microsoft 365 Message Center (future)
        
        SERVICE EXTRACTION PATTERNS:
        - "X is retiring" → service X
        - "retirement of X" → service X  
        - "X end of life" → service X
        - "X to retire" → service X
        
        SEARCH QUERY GENERATION:
        - {service} retirement
        - {service} deprecation announcement
        - {service} end of support
        
        Args:
            title: Issue title with potential service names
            description: Full issue description
            services: List of detected services (may be empty)
            
        Returns:
            List of retirement info dicts with:
            - service: Extracted or provided service name
            - feature: "Retirement Information" (placeholder)
            - retirement_date: "See Microsoft Learn for details"
            - announcement_url: Direct Microsoft Learn search link
            - migration_guide: General Azure migration guidance
            - source: "online_search" to distinguish from JSON results
        """
        results = []
        
        # Extract key terms for retirement search
        import re
        text_combined = f"{title} {description}".lower()
        
        # PATTERN MATCHING: Identify service/product names mentioned
        service_matches = []
        
        # If services already provided, use them
        if services:
            service_matches = services[:3]  # Top 3 services
        else:
            # REGEX PATTERNS to extract service names from issue text
            # Looks for capitalized terms before/after retirement keywords
            patterns = [
                r'([A-Z][A-Za-z\s]+?)\s+(?:is\s+)?(?:retir|deprecat|end of life)',  # "Service X is retiring"
                r'(?:retirement|deprecation)\s+(?:of\s+)?([A-Z][A-Za-z\s]+)',        # "retirement of Service X"
                r'([A-Z][A-Za-z\s]+?)\s+to\s+retire'                                 # "Service X to retire"
            ]
            for pattern in patterns:
                matches = re.findall(pattern, title + ' ' + description)
                service_matches.extend([m.strip() for m in matches if len(m.strip()) > 3])
        
        if not service_matches:
            # FALLBACK: Use first few words of title if no service detected
            service_matches = [' '.join(title.split()[:3])]
        
        # BUILD COMPREHENSIVE SEARCH QUERIES
        # Each service gets multiple query variations for thorough coverage
        search_queries = []
        for service in service_matches[:2]:  # Top 2 to avoid too many searches
            search_queries.extend([
                f"{service} retirement",
                f"{service} deprecation announcement",
                f"{service} end of support"
            ])
        
        print(f"[RetirementCheck] Online search - Services: {service_matches}")
        print(f"[RetirementCheck] Online search - Queries: {search_queries[:3]}")
        
        # CREATE PLACEHOLDER RESULTS that direct to online search
        # The actual MCP Microsoft Learn search is called from app.py perform_search route
        # These placeholders ensure UI shows something useful even if MCP call fails
        for idx, service in enumerate(service_matches[:2]):
            query = search_queries[idx] if idx < len(search_queries) else f"{service} retirement"
            results.append({
                'service': service,
                'feature': 'Retirement Information',
                'retirement_date': 'See Microsoft Learn for details',
                'announcement_url': f"https://learn.microsoft.com/en-us/search/?terms={'+'.join(query.split())}",
                'migration_guide': 'https://learn.microsoft.com/azure/advisor/advisor-how-to-plan-migration-workloads-service-retirement',
                'extension_available': False,
                'extension_url': None,
                'replacement': 'Check announcement for alternatives',
                'source': 'online_search'
            })
        
        return results


def search_microsoft_learn(query: str, max_results: int = 10) -> List[SearchResult]:
    """
    Placeholder for Microsoft Learn search
    
    This function will be called from app.py where MCP tools are available.
    The actual search will use mcp_microsoft_doc_microsoft_docs_search.
    
    Args:
        query: Search query
        max_results: Maximum number of results
        
    Returns:
        List of SearchResult objects
    """
    # This is implemented in app.py using MCP tools
    return []
