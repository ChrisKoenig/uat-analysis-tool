"""
Embedding Service
Generates and caches text embeddings using Azure OpenAI
Designed as independent service for future agent architecture
"""

import hashlib
from typing import List, Optional, Dict, Any
from openai import AzureOpenAI
import numpy as np

from shared.ai_config import get_config
from shared.cache_manager import CacheManager


class EmbeddingService:
    """
    Service for generating text embeddings with smart caching
    
    Features:
    - API-first with cache fallback
    - 7-day cache TTL with auto-refresh
    - Batch embedding support
    - Designed as independent agent
    """
    
    def __init__(self):
        self.config = get_config()
        self.azure_config = self.config.azure_openai
        self.caching_config = self.config.caching
        
        # Initialize Azure OpenAI client with timeout
        # Supports both Azure AD (managed identity / browser) and API key auth.
        # Azure AD is the default for Azure deployments (no API keys allowed).
        use_aad = self.azure_config.use_aad if hasattr(self.azure_config, 'use_aad') else False
        
        if use_aad:
            # Use shared credential (single auth for all services)
            print(f"[EmbeddingService] 🔐 Using Azure AD authentication (shared credential)...")
            from shared.shared_auth import get_credential, get_credential_type
            from azure.identity import get_bearer_token_provider
            credential = get_credential()
            print(f"[EmbeddingService] Using shared credential (type: {get_credential_type()})")
            token_provider = get_bearer_token_provider(
                credential,
                "https://cognitiveservices.azure.com/.default"
            )
            self.client = AzureOpenAI(
                azure_endpoint=self.azure_config.endpoint,
                azure_ad_token_provider=token_provider,
                api_version=self.azure_config.api_version,
                timeout=10.0  # 10 second timeout prevents hanging on connection errors
            )
        else:
            # Fallback to API key authentication
            print(f"[EmbeddingService] 🔑 Using API key authentication...")
            self.client = AzureOpenAI(
                azure_endpoint=self.azure_config.endpoint,
                api_key=self.azure_config.api_key,
                api_version=self.azure_config.api_version,
                timeout=10.0  # 10 second timeout prevents hanging on connection errors
            )
        
        # Get service-specific configuration
        service_config = self.config.get_service_config("embedding_service")
        
        # Initialize cache manager
        self.cache = CacheManager(
            cache_path=service_config["cache_path"],
            ttl_days=self.caching_config.ttl_days,
            api_first=self.caching_config.api_first,
            slow_threshold=self.caching_config.slow_threshold_seconds
        )
        
        self.model = service_config["model"]
        self.deployment = service_config["deployment"]
        
        print(f"[EmbeddingService] Initialized with model: {self.model}")
        print(f"[EmbeddingService] Deployment: {self.deployment}")
        print(f"[EmbeddingService] Cache: {service_config['cache_path']}")
    
    def _make_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        # Include model in key to handle model upgrades
        key_data = f"{self.model}:{text}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def _call_embedding_api(self, text: str) -> List[float]:
        """Call Azure OpenAI embedding API"""
        try:
            print(f"[EmbeddingService] Calling API - Endpoint: {self.azure_config.endpoint}")
            print(f"[EmbeddingService] Deployment: {self.deployment}")
            response = self.client.embeddings.create(
                input=text,
                model=self.deployment  # Use deployment name for Azure
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"[EmbeddingService] ❌ API call failed!")
            print(f"[EmbeddingService] Error type: {type(e).__name__}")
            print(f"[EmbeddingService] Error message: {str(e)}")
            import traceback
            print(f"[EmbeddingService] Traceback: {traceback.format_exc()}")
            raise
    
    def embed(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        Generate embedding for single text
        
        Args:
            text: Text to embed
            use_cache: Whether to use cache (default True)
            
        Returns:
            numpy array of embeddings
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        text = text.strip()
        cache_key = self._make_cache_key(text)
        
        if use_cache and self.caching_config.enabled:
            # Use API-first strategy
            embedding, source = self.cache.get_or_compute_with_api_first(
                cache_key,
                lambda: self._call_embedding_api(text)
            )
            print(f"[EmbeddingService] Embedding from: {source}")
        else:
            # Direct API call without cache
            print(f"[EmbeddingService] Direct API call (cache disabled)")
            embedding = self._call_embedding_api(text)
        
        return np.array(embedding)
    
    def embed_batch(self, texts: List[str], use_cache: bool = True) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache
            
        Returns:
            List of numpy arrays
        """
        if not texts:
            return []
        
        embeddings = []
        for text in texts:
            try:
                embedding = self.embed(text, use_cache=use_cache)
                embeddings.append(embedding)
            except Exception as e:
                print(f"[EmbeddingService] Error embedding text: {e}")
                # Use zero vector as fallback
                embeddings.append(np.zeros(3072))  # text-embedding-3-large dimension
        
        return embeddings
    
    def embed_context(
        self, 
        title: str, 
        description: str, 
        impact: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, np.ndarray]:
        """
        Embed a context (title + description + impact) with separate embeddings
        
        Args:
            title: Issue title
            description: Issue description
            impact: Business impact (optional)
            use_cache: Whether to use cache
            
        Returns:
            Dictionary with separate embeddings and combined embedding
        """
        result = {
            "title_embedding": self.embed(title, use_cache=use_cache),
            "description_embedding": self.embed(description, use_cache=use_cache)
        }
        
        if impact and impact.strip():
            result["impact_embedding"] = self.embed(impact, use_cache=use_cache)
        
        # Create combined embedding (weighted average)
        combined_parts = [
            result["title_embedding"] * 2.0,  # Title more important
            result["description_embedding"] * 1.0
        ]
        
        if "impact_embedding" in result:
            combined_parts.append(result["impact_embedding"] * 0.5)  # Impact least important
        
        result["combined_embedding"] = np.mean(combined_parts, axis=0)
        
        return result
    
    def cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding
            embedding2: Second embedding
            
        Returns:
            Similarity score (0-1)
        """
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()
    
    def clear_cache(self) -> None:
        """Clear embedding cache"""
        self.cache.clear()
    
    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries"""
        return self.cache.cleanup_expired()


def test_embedding_service():
    """Test the embedding service"""
    print("Embedding Service Test")
    print("=" * 50)
    
    try:
        service = EmbeddingService()
        
        # Test single embedding
        text = "Azure SQL Managed Instance availability in West Europe region"
        print(f"\nTesting single embedding for: '{text[:50]}...'")
        
        embedding = service.embed(text)
        print(f"Embedding dimension: {embedding.shape}")
        print(f"First 5 values: {embedding[:5]}")
        
        # Test cache hit
        print("\nTesting cache hit (should be fast)...")
        embedding2 = service.embed(text)
        print(f"Same embedding: {np.allclose(embedding, embedding2)}")
        
        # Test context embedding
        print("\nTesting context embedding...")
        context = service.embed_context(
            title="SQL MI deployment issue",
            description="Unable to deploy SQL Managed Instance in West Europe",
            impact="Blocking production deployment"
        )
        print(f"Generated embeddings: {list(context.keys())}")
        
        # Test similarity
        print("\nTesting similarity...")
        text2 = "SQL Managed Instance not available in Western Europe"
        embedding3 = service.embed(text2)
        similarity = service.cosine_similarity(embedding, embedding3)
        print(f"Similarity between related texts: {similarity:.4f}")
        
        text3 = "Azure Functions deployment failed"
        embedding4 = service.embed(text3)
        similarity2 = service.cosine_similarity(embedding, embedding4)
        print(f"Similarity between unrelated texts: {similarity2:.4f}")
        
        # Cache stats
        print("\nCache Statistics:")
        stats = service.get_cache_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n✓ Embedding service test complete!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        print("\nMake sure to set environment variables:")
        print("  - AZURE_OPENAI_ENDPOINT")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_EMBEDDING_DEPLOYMENT (optional)")


if __name__ == "__main__":
    test_embedding_service()
