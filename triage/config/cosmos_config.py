"""
Cosmos DB Configuration
=======================

Manages connection to Azure Cosmos DB for the Triage Management System.
Handles database and container initialization with support for both
local development (DefaultAzureCredential) and production deployment
(ManagedIdentityCredential).

Cosmos DB Structure:
    Database: triage-management
    Containers:
        - rules:            Atomic conditions (field + operator + value)
        - actions:          Atomic field assignments
        - triggers:         Triggers (rule chains → route)
        - routes:           Action collections
        - evaluations:      Per-item rule evaluation results
        - analysis-results: Structured analysis output
        - field-schema:     Field definitions and metadata
        - audit-log:        Change tracking for all entities
        - corrections:      User corrections to AI classifications (fine-tuning)

Configuration is loaded from Azure Key Vault with environment variable fallback.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any

from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import (
    DefaultAzureCredential,
    ManagedIdentityCredential,
    InteractiveBrowserCredential,
    SharedTokenCacheCredential,
    AzureCliCredential,
    ChainedTokenCredential,
    TokenCachePersistenceOptions,
)

logger = logging.getLogger("triage.config.cosmos")

# Add parent directory to path for keyvault_config access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from keyvault_config import get_keyvault_config


# =============================================================================
# Container Definitions
# =============================================================================
# Each container is defined with its partition key and description.
# Partition keys are chosen based on primary access patterns.

CONTAINER_DEFINITIONS = {
    "rules": {
        "partition_key": "/status",
        "description": "Atomic rule conditions (field + operator + value)"
    },
    "actions": {
        "partition_key": "/status",
        "description": "Atomic field assignments (field + operation + value)"
    },
    "triggers": {
        "partition_key": "/status",
        "description": "Triggers (rule chains with AND/OR logic)"
    },
    "routes": {
        "partition_key": "/status",
        "description": "Action collections (groups of actions to execute)"
    },
    "evaluations": {
        "partition_key": "/workItemId",
        "description": "Per-item rule evaluation results and routing decisions"
    },
    "analysis-results": {
        "partition_key": "/workItemId",
        "description": "Structured analysis output from the analysis engine"
    },
    "field-schema": {
        "partition_key": "/source",
        "description": "Field definitions with operator mappings and metadata"
    },
    "audit-log": {
        "partition_key": "/entityType",
        "description": "Change history for all entities (who/when/what)"
    },
    "corrections": {
        "partition_key": "/workItemId",
        "description": "User corrections to AI classifications, fed back into fine-tuning"
    },
    "training-signals": {
        "partition_key": "/workItemId",
        "description": "Active learning signals from LLM/Pattern disagreements resolved by humans"
    },
    "triage-teams": {
        "partition_key": "/status",
        "description": "Triage team configurations (team name, ADO query, display order)"
    },
    "servicetree-catalog": {
        "partition_key": "/solutionArea",
        "description": "ServiceTree service catalog with admin overrides for triage routing"
    }
}


# =============================================================================
# Default Configuration
# =============================================================================
# These can be overridden by Key Vault secrets or environment variables.

DEFAULT_DATABASE_NAME = "triage-management"
DEFAULT_COSMOS_ENDPOINT = None  # Must be configured
DEFAULT_COSMOS_KEY = None       # Only used if not using AAD auth


class CosmosDBConfig:
    """
    Manages Cosmos DB connection and container access for the Triage System.
    
    Supports two authentication modes:
        1. Azure AD (DefaultAzureCredential) - preferred for production
        2. Connection string / key - for local development if needed
    
    Usage:
        config = CosmosDBConfig()
        rules_container = config.get_container("rules")
        
        # Or use the convenience method
        items = config.get_container("rules").query_items(
            query="SELECT * FROM c WHERE c.status = 'active'",
            partition_key="active"
        )
    
    Environment Variables / Key Vault Secrets:
        COSMOS_ENDPOINT:     Cosmos DB account endpoint URL
        COSMOS_KEY:          Account key (optional if using AAD)
        COSMOS_DATABASE:     Database name (default: triage-management)
        COSMOS_USE_AAD:      Use Azure AD authentication (default: true)
    """
    
    def __init__(self):
        """Initialize Cosmos DB configuration (lazy - no connection until needed)"""
        self._client: Optional[CosmosClient] = None
        self._database = None
        self._containers: Dict[str, Any] = {}
        self._initialized = False
        self._in_memory = False
        
        # Load configuration from Key Vault / environment
        self._load_config()
    
    def _load_config(self):
        """
        Load Cosmos DB configuration from Key Vault with env var fallback.
        
        Priority: Key Vault → Environment Variable → Default
        """
        kv_config = get_keyvault_config()
        
        # Cosmos DB endpoint (required)
        self.endpoint = (
            kv_config.get_secret("COSMOS_ENDPOINT") or
            os.environ.get("COSMOS_ENDPOINT") or
            DEFAULT_COSMOS_ENDPOINT
        )
        
        # Cosmos DB key (optional - not needed with AAD auth)
        self.key = (
            kv_config.get_secret("COSMOS_KEY") or
            os.environ.get("COSMOS_KEY") or
            DEFAULT_COSMOS_KEY
        )
        
        # Database name
        self.database_name = (
            os.environ.get("COSMOS_DATABASE") or
            DEFAULT_DATABASE_NAME
        )
        
        # Authentication mode
        use_aad_str = (
            kv_config.get_secret("COSMOS_USE_AAD") or
            os.environ.get("COSMOS_USE_AAD", "true")
        )
        self.use_aad = use_aad_str.lower() in ("true", "1", "yes")
        
        # Tenant ID for AAD auth (required when user's home tenant differs from Cosmos account tenant)
        self.tenant_id = (
            kv_config.get_secret("COSMOS_TENANT_ID") or
            os.environ.get("COSMOS_TENANT_ID")
        )
        
    def _get_client(self) -> CosmosClient:
        """
        Lazy initialization of Cosmos DB client.
        
        Uses ManagedIdentityCredential if AZURE_CLIENT_ID is set (production),
        otherwise uses DefaultAzureCredential (local development).
        Falls back to key-based auth if AAD is disabled.
        
        Returns:
            CosmosClient instance
            
        Raises:
            ValueError: If endpoint is not configured
            Exception: If connection fails
        """
        if self._client is None:
            if not self.endpoint:
                raise ValueError(
                    "Cosmos DB endpoint not configured. "
                    "Set COSMOS_ENDPOINT in Key Vault or environment variables."
                )
            
            try:
                if self.use_aad:
                    # Azure AD authentication (preferred)
                    managed_identity_client_id = os.environ.get('AZURE_CLIENT_ID')
                    
                    if managed_identity_client_id:
                        # Production: Use managed identity
                        credential = ManagedIdentityCredential(
                            client_id=managed_identity_client_id
                        )
                        auth_method = f"Managed Identity ({managed_identity_client_id[:8]}...)"
                    else:
                        # Development: Reuse the shared credential from shared_auth
                        # so all services (OpenAI, ADO, Cosmos) share ONE auth session.
                        try:
                            from shared_auth import get_credential
                            credential = get_credential()
                            auth_method = "SharedAuth (shared credential)"
                            logger.info("  Using shared credential from shared_auth")
                        except Exception as e:
                            logger.warning("  shared_auth unavailable (%s), falling back to credential chain", e)
                            # Fallback: build a credential chain
                            if self.tenant_id:
                                logger.info("  Using tenant: %s", self.tenant_id)
                                cache_opts = TokenCachePersistenceOptions(
                                    name="gcs-cosmos-auth"
                                )
                                credential = ChainedTokenCredential(
                                    SharedTokenCacheCredential(
                                        tenant_id=self.tenant_id,
                                        cache_persistence_options=cache_opts,
                                    ),
                                    AzureCliCredential(
                                        tenant_id=self.tenant_id,
                                    ),
                                    InteractiveBrowserCredential(
                                        tenant_id=self.tenant_id,
                                        cache_persistence_options=cache_opts,
                                    ),
                                )
                                auth_method = f"ChainedTokenCredential (tenant: {self.tenant_id[:8]}...)"
                            else:
                                credential = DefaultAzureCredential()
                                auth_method = "DefaultAzureCredential"
                    
                    self._client = CosmosClient(
                        url=self.endpoint,
                        credential=credential
                    )
                    logger.info("Connected to Cosmos DB: %s", self.endpoint)
                    logger.info("  Authentication: %s", auth_method)
                    
                elif self.key:
                    # Key-based authentication (fallback)
                    self._client = CosmosClient(
                        url=self.endpoint,
                        credential=self.key
                    )
                    logger.info("Connected to Cosmos DB: %s", self.endpoint)
                    logger.info("  Authentication: Account Key")
                    
                else:
                    raise ValueError(
                        "No authentication configured. "
                        "Set COSMOS_USE_AAD=true or provide COSMOS_KEY."
                    )
                    
            except Exception as e:
                logger.error("Could not connect to Cosmos DB: %s", e)
                raise
                
        return self._client
    
    def _ensure_database(self):
        """
        Ensure the database exists, creating it if necessary.
        
        Uses 400 RU/s shared throughput across all containers.
        """
        if self._database is None:
            client = self._get_client()
            try:
                self._database = client.create_database_if_not_exists(
                    id=self.database_name
                )
                logger.info("Database '%s' ready", self.database_name)
            except exceptions.CosmosHttpResponseError as e:
                logger.error("ERROR creating database: %s", e)
                raise
    
    def _ensure_containers(self):
        """
        Ensure all containers exist with correct partition keys.
        Creates missing containers automatically on first access.
        Falls back to in-memory storage if no Cosmos DB endpoint is configured.
        """
        if self._initialized:
            return
        
        # ── In-memory fallback when Cosmos DB is not configured ──
        if not self.endpoint:
            from .memory_store import InMemoryContainer, seed_containers
            logger.warning(
                "COSMOS_ENDPOINT not set — using in-memory storage "
                "(data will not persist across restarts)"
            )
            self._in_memory = True
            for name, defn in CONTAINER_DEFINITIONS.items():
                self._containers[name] = InMemoryContainer(
                    container_name=name,
                    partition_key_path=defn["partition_key"]
                )
                logger.info(
                    "  [MEM] Container '%s' ready (partition: %s)",
                    name, defn['partition_key'],
                )
            seed_containers(self._containers)
            self._initialized = True
            logger.info(
                "All %d containers initialized (in-memory mode)",
                len(CONTAINER_DEFINITIONS)
            )
            return
        
        # ── Real Cosmos DB initialization ──
        self._ensure_database()
        
        for container_name, definition in CONTAINER_DEFINITIONS.items():
            try:
                container = self._database.create_container_if_not_exists(
                    id=container_name,
                    partition_key=PartitionKey(path=definition["partition_key"])
                )
                self._containers[container_name] = container
                logger.info(
                    "  [OK] Container '%s' ready (partition: %s)",
                    container_name, definition['partition_key'],
                )
            except exceptions.CosmosHttpResponseError as e:
                logger.error("  [ERROR] Container '%s': %s", container_name, e)
                raise
        
        self._initialized = True
        logger.info("All %d containers initialized", len(CONTAINER_DEFINITIONS))
    
    def get_container(self, container_name: str):
        """
        Get a Cosmos DB container proxy for performing operations.
        
        Initializes the database and all containers on first access.
        
        Args:
            container_name: Name of the container (e.g., 'rules', 'evaluations')
            
        Returns:
            ContainerProxy for the requested container
            
        Raises:
            ValueError: If container name is not recognized
        """
        if container_name not in CONTAINER_DEFINITIONS:
            raise ValueError(
                f"Unknown container: '{container_name}'. "
                f"Valid containers: {list(CONTAINER_DEFINITIONS.keys())}"
            )
        
        # Ensure everything is initialized
        if not self._initialized:
            self._ensure_containers()
        
        return self._containers[container_name]
    
    def get_all_container_names(self) -> list:
        """Get list of all container names in the triage database"""
        return list(CONTAINER_DEFINITIONS.keys())
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the Cosmos DB connection.
        
        Returns:
            Dict with status, endpoint, database, and container details
        """
        try:
            self._ensure_containers()
            status = "healthy (in-memory)" if self._in_memory else "healthy"
            return {
                "status": status,
                "endpoint": self.endpoint or "in-memory",
                "database": self.database_name,
                "containers": {
                    name: {
                        "status": "ready",
                        "partition_key": defn["partition_key"]
                    }
                    for name, defn in CONTAINER_DEFINITIONS.items()
                },
                "auth_mode": "in-memory" if self._in_memory else ("aad" if self.use_aad else "key")
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "endpoint": self.endpoint,
                "database": self.database_name
            }


# =============================================================================
# Module-level singleton
# =============================================================================
# Provides a single shared instance across the application.

_cosmos_config: Optional[CosmosDBConfig] = None


def get_cosmos_config() -> CosmosDBConfig:
    """
    Get the shared CosmosDBConfig singleton.
    
    Returns:
        CosmosDBConfig instance (created on first call)
    """
    global _cosmos_config
    if _cosmos_config is None:
        _cosmos_config = CosmosDBConfig()
    return _cosmos_config
