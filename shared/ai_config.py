"""
AI Configuration System
Centralized configuration for Azure OpenAI, embeddings, LLM classification, and caching.
Designed for modular agent-based architecture.

Configuration Resolution Order:
  1. Azure Key Vault (via keyvault_config.get_keyvault_config())
  2. Environment variables (via .env / App Service settings)

Deployment Notes:
  - Dev: Key Vault = kv-gcs-dev-gg4a6y, OpenAI = OpenAI-bp-NorthCentral
  - Pre-Prod: Key Vault = kv-aitriage, OpenAI = openai-aitriage-nonprod
  - Corrections are stored in Cosmos DB (corrections container), NOT on the file system.
    The validate() method no longer checks for corrections.json on disk.
"""

import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

# Mapping from config key → AppConfig property name
_KEY_TO_APP_CONFIG = {
    "AZURE_OPENAI_ENDPOINT": "openai_endpoint",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embedding_deployment",
    "AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT": "classification_deployment",
}

# True secrets that must come from Key Vault (not config)
_TRUE_SECRETS = {"AZURE_OPENAI_API_KEY"}


def _get_config_value(key: str, default: str = "") -> str:
    """Get a configuration value.

    True secrets → Key Vault → env var.
    Config values → AppConfig → env var.
    """
    # True secrets: Key Vault first
    if key in _TRUE_SECRETS:
        try:
            from shared.keyvault_config import get_keyvault_config
            value = get_keyvault_config().get_secret(key)
            if value:
                return value
        except Exception:
            pass
        return os.environ.get(key, default)

    # Config values: AppConfig first (single source of truth)
    attr = _KEY_TO_APP_CONFIG.get(key)
    if attr:
        try:
            from shared.config import get_app_config
            cfg_val = getattr(get_app_config(), attr, None)
            if cfg_val:
                return cfg_val
        except Exception:
            pass

    return os.environ.get(key, default)

@dataclass
class AzureOpenAIConfig:
    """Azure OpenAI service configuration - loads from Key Vault first, then .env"""
    endpoint: str = field(default_factory=lambda: _get_config_value("AZURE_OPENAI_ENDPOINT", ""))
    api_key: str = field(default_factory=lambda: _get_config_value("AZURE_OPENAI_API_KEY", ""))
    api_version: str = "2024-08-01-preview"  # Working API version for gpt-4o deployments
    use_aad: bool = field(default_factory=lambda: _get_config_value("AZURE_OPENAI_USE_AAD", "true").lower() == "true")
    
    # Model deployments
    embedding_model: str = "text-embedding-3-large"  # High-quality embeddings
    classification_model: str = "gpt-4o"  # GPT-4 Omni for reasoning
    
    # Deployment names (Azure-specific)
    embedding_deployment: str = field(default_factory=lambda: _get_config_value("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"))
    classification_deployment: str = field(default_factory=lambda: _get_config_value("AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT", "gpt-4o-standard"))
    
    # Model parameters
    temperature: float = 0.1  # Low temperature for consistency
    max_tokens: int = 1000  # Sufficient for classification reasoning
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration is complete"""
        if not self.endpoint:
            return False, "AZURE_OPENAI_ENDPOINT environment variable not set"
        if not self.use_aad and not self.api_key:
            return False, "AZURE_OPENAI_API_KEY environment variable not set (or enable Azure AD with AZURE_OPENAI_USE_AAD=true)"
        return True, None


@dataclass
class CachingConfig:
    """Smart caching configuration with API-first strategy"""
    enabled: bool = True
    cache_dir: str = os.environ.get("AI_CACHE_DIR", os.path.join("apps", "triage", "cache", "ai_cache"))
    
    # TTL strategy
    ttl_days: int = 7  # User requirement: 7-day cache refresh
    api_first: bool = True  # Try API first, cache as fallback
    slow_threshold_seconds: float = 3.0  # Consider API "slow" after 3 seconds
    
    # Cache types
    embedding_cache_enabled: bool = True
    classification_cache_enabled: bool = True
    vector_search_cache_enabled: bool = True
    
    def get_cache_path(self, cache_type: str) -> str:
        """Get full path for specific cache type"""
        return os.path.join(self.cache_dir, f"{cache_type}_cache.json")


@dataclass
class VectorSearchConfig:
    """Vector search and similarity configuration"""
    similarity_threshold: float = 0.75  # Cosine similarity threshold
    top_k_results: int = 10  # Number of similar items to return
    use_gpu: bool = False  # Use GPU acceleration if available
    
    # Similarity metrics
    metric: str = "cosine"  # cosine, euclidean, or dot_product


@dataclass
class FineTuningConfig:
    """Fine-tuning preparation configuration"""
    corrections_file: str = "corrections.json"
    training_output_dir: str = "training_data"
    validation_split: float = 0.2  # 20% for validation
    
    # Fine-tuning parameters
    n_epochs: int = 3
    batch_size: int = 4
    learning_rate_multiplier: float = 0.1


@dataclass
class PatternMatchingConfig:
    """Configuration for legacy pattern matching used as AI features"""
    use_as_features: bool = True  # Use pattern matching as features for AI
    use_as_fallback: bool = True  # Fall back to patterns if AI fails
    boost_confidence_when_agree: float = 0.15  # Boost AI confidence when patterns agree


@dataclass
class AIConfig:
    """Main AI configuration container"""
    azure_openai: AzureOpenAIConfig = field(default_factory=AzureOpenAIConfig)
    caching: CachingConfig = field(default_factory=CachingConfig)
    vector_search: VectorSearchConfig = field(default_factory=VectorSearchConfig)
    fine_tuning: FineTuningConfig = field(default_factory=FineTuningConfig)
    pattern_matching: PatternMatchingConfig = field(default_factory=PatternMatchingConfig)
    
    # Agent architecture flags
    agent_mode: bool = False  # Enable when running as independent agents
    service_discovery_enabled: bool = False  # For future agent orchestration
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate all configurations.
        
        Note (Feb 27, 2026): File-system corrections.json validation was removed.
        Corrections are stored in Cosmos DB (corrections container) and loaded
        by the field portal / admin routes. The FineTuningConfig.corrections_file
        field is retained for legacy local-dev compatibility but is not validated.
        """
        errors = []
        
        # Validate Azure OpenAI
        valid, error = self.azure_openai.validate()
        if not valid:
            errors.append(f"Azure OpenAI: {error}")
        
        # Validate cache directory
        if self.caching.enabled:
            os.makedirs(self.caching.cache_dir, exist_ok=True)
        
        # Note: Corrections are stored in Cosmos DB (corrections container),
        # no file-system validation needed.
        
        return len(errors) == 0, errors
    
    def get_service_config(self, service_name: str) -> Dict[str, Any]:
        """Get configuration for specific AI service (agent-ready)"""
        configs = {
            "embedding_service": {
                "model": self.azure_openai.embedding_model,
                "deployment": self.azure_openai.embedding_deployment,
                "cache_enabled": self.caching.embedding_cache_enabled,
                "cache_path": self.caching.get_cache_path("embeddings")
            },
            "llm_classifier": {
                "model": self.azure_openai.classification_model,
                "deployment": self.azure_openai.classification_deployment,
                "temperature": self.azure_openai.temperature,
                "max_tokens": self.azure_openai.max_tokens,
                "cache_enabled": self.caching.classification_cache_enabled,
                "cache_path": self.caching.get_cache_path("classifications")
            },
            "vector_search": {
                "similarity_threshold": self.vector_search.similarity_threshold,
                "top_k": self.vector_search.top_k_results,
                "metric": self.vector_search.metric,
                "cache_enabled": self.caching.vector_search_cache_enabled,
                "cache_path": self.caching.get_cache_path("vector_searches")
            }
        }
        return configs.get(service_name, {})


# Global configuration instance (singleton pattern)
_config_instance: Optional[AIConfig] = None

def get_config() -> AIConfig:
    """Get global AI configuration instance"""
    global _config_instance
    if _config_instance is None:
        _config_instance = AIConfig()
    return _config_instance

def validate_config() -> None:
    """Validate configuration and raise exception if invalid"""
    config = get_config()
    valid, errors = config.validate()
    if not valid:
        error_msg = "AI Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

def reload_config() -> AIConfig:
    """Reload configuration from environment (useful for testing)"""
    global _config_instance
    _config_instance = None
    return get_config()


if __name__ == "__main__":
    # Test configuration
    print("AI Configuration Test")
    print("=" * 50)
    
    config = get_config()
    valid, errors = config.validate()
    
    if valid:
        print("✓ Configuration is valid!")
        print(f"\nEmbedding Model: {config.azure_openai.embedding_model}")
        print(f"Classification Model: {config.azure_openai.classification_model}")
        print(f"Cache TTL: {config.caching.ttl_days} days")
        print(f"API-First Strategy: {config.caching.api_first}")
        print(f"Pattern Matching as Features: {config.pattern_matching.use_as_features}")
        print(f"Agent Mode: {config.agent_mode}")
    else:
        print("✗ Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        print("\nSet environment variables:")
        print("  - AZURE_OPENAI_ENDPOINT")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_EMBEDDING_DEPLOYMENT (optional)")
        print("  - AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT (optional)")
