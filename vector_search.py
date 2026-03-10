"""
Vector Search Service
Semantic similarity search using embeddings
Designed as independent service for future agent architecture
"""

import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from embedding_service import EmbeddingService
from cache_manager import CacheManager
from ai_config import get_config


@dataclass
class SearchResult:
    """Single search result with similarity score"""
    item_id: str
    title: str
    description: str
    similarity: float
    metadata: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "item_id": self.item_id,
            "title": self.title,
            "description": self.description,
            "similarity": self.similarity,
            "metadata": self.metadata
        }


class VectorSearchService:
    """
    Semantic similarity search service
    
    Features:
    - Fast cosine similarity search
    - In-memory vector index
    - Support for multiple collections (UATs, issues, etc.)
    - Threshold-based filtering
    - Designed as independent agent
    """
    
    def __init__(self, embedding_service: EmbeddingService = None):
        self.config = get_config()
        self.vector_config = self.config.vector_search
        
        # Reuse provided embedding service or create new one
        self.embedding_service = embedding_service or EmbeddingService()
        
        # Get service-specific configuration
        service_config = self.config.get_service_config("vector_search")
        
        # Initialize cache for search results
        self.cache = CacheManager(
            cache_path=service_config["cache_path"],
            ttl_days=self.config.caching.ttl_days,
            api_first=False,  # Search results can use cache-first
            slow_threshold=self.config.caching.slow_threshold_seconds
        )
        
        # Vector index storage (collection_name -> list of items with embeddings)
        self.vector_index: Dict[str, List[Dict]] = {}
        
        print(f"[VectorSearchService] Initialized")
        print(f"[VectorSearchService] Similarity threshold: {self.vector_config.similarity_threshold}")
        print(f"[VectorSearchService] Top-K results: {self.vector_config.top_k_results}")
    
    def index_items(
        self,
        collection_name: str,
        items: List[Dict[str, Any]],
        force_reindex: bool = False
    ) -> int:
        """
        Index items into vector collection
        
        Args:
            collection_name: Name of the collection (e.g., "uats", "issues")
            items: List of items with 'id', 'title', 'description' keys
            force_reindex: Force re-embedding even if already indexed
            
        Returns:
            Number of items indexed
        """
        if not items:
            print(f"[VectorSearchService] No items to index for collection '{collection_name}'")
            return 0
        
        print(f"[VectorSearchService] Indexing {len(items)} items into '{collection_name}'...")
        
        indexed_items = []
        for item in items:
            try:
                # Generate embeddings for title and description
                title = item.get("title", "")
                description = item.get("description", "")
                
                if not title and not description:
                    print(f"[VectorSearchService] Skipping item {item.get('id')} - no text")
                    continue
                
                # Create combined text for embedding
                combined_text = f"{title}\n{description}"
                
                # Generate embedding (uses cache automatically)
                embedding = self.embedding_service.embed(combined_text, use_cache=not force_reindex)
                
                # Store indexed item
                indexed_items.append({
                    "id": item.get("id", f"item_{len(indexed_items)}"),
                    "title": title,
                    "description": description,
                    "embedding": embedding,
                    "metadata": item.get("metadata", {})
                })
                
            except Exception as e:
                print(f"[VectorSearchService] Error indexing item {item.get('id')}: {e}")
                continue
        
        # Store in vector index
        self.vector_index[collection_name] = indexed_items
        
        print(f"[VectorSearchService] Successfully indexed {len(indexed_items)} items")
        return len(indexed_items)
    
    def search(
        self,
        query: str,
        collection_name: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        use_cache: bool = True
    ) -> List[SearchResult]:
        """
        Search for similar items using semantic similarity
        
        Args:
            query: Query text
            collection_name: Name of collection to search
            top_k: Number of results (default from config)
            similarity_threshold: Minimum similarity score (default from config)
            use_cache: Whether to cache results
            
        Returns:
            List of SearchResults ordered by similarity (highest first)
        """
        if not query:
            raise ValueError("Query cannot be empty")
        
        if collection_name not in self.vector_index:
            print(f"[VectorSearchService] Collection '{collection_name}' not indexed")
            return []
        
        collection = self.vector_index[collection_name]
        if not collection:
            print(f"[VectorSearchService] Collection '{collection_name}' is empty")
            return []
        
        # Use config defaults if not specified
        if top_k is None:
            top_k = self.vector_config.top_k_results
        if similarity_threshold is None:
            similarity_threshold = self.vector_config.similarity_threshold
        
        print(f"[VectorSearchService] Searching '{collection_name}' for: '{query[:50]}...'")
        
        # Generate query embedding
        query_embedding = self.embedding_service.embed(query, use_cache=use_cache)
        
        # Calculate similarities
        similarities = []
        for item in collection:
            item_embedding = item["embedding"]
            similarity = self.embedding_service.cosine_similarity(query_embedding, item_embedding)
            
            if similarity >= similarity_threshold:
                similarities.append({
                    "item": item,
                    "similarity": float(similarity)
                })
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Take top-k results
        top_results = similarities[:top_k]
        
        print(f"[VectorSearchService] Found {len(top_results)} results (threshold: {similarity_threshold:.2f})")
        
        # Convert to SearchResult objects
        results = [
            SearchResult(
                item_id=r["item"]["id"],
                title=r["item"]["title"],
                description=r["item"]["description"],
                similarity=r["similarity"],
                metadata=r["item"].get("metadata")
            )
            for r in top_results
        ]
        
        return results
    
    def search_with_context(
        self,
        title: str,
        description: str,
        collection_name: str,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[SearchResult]:
        """
        Search using title + description context
        
        Args:
            title: Query title
            description: Query description
            collection_name: Collection to search
            top_k: Number of results
            similarity_threshold: Minimum similarity
            
        Returns:
            List of SearchResults
        """
        combined_query = f"{title}\n{description}"
        return self.search(
            query=combined_query,
            collection_name=collection_name,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )
    
    def find_similar_issues(
        self,
        title: str,
        description: str,
        top_k: int = 5
    ) -> List[SearchResult]:
        """
        Find similar issues/UATs for duplicate detection
        
        Args:
            title: Issue title
            description: Issue description
            top_k: Number of similar items to return
            
        Returns:
            List of similar issues
        """
        # Try searching UATs collection first
        if "uats" in self.vector_index:
            results = self.search_with_context(
                title=title,
                description=description,
                collection_name="uats",
                top_k=top_k,
                similarity_threshold=0.70  # Higher threshold for duplicate detection
            )
            if results:
                return results
        
        # Try searching issues collection
        if "issues" in self.vector_index:
            results = self.search_with_context(
                title=title,
                description=description,
                collection_name="issues",
                top_k=top_k,
                similarity_threshold=0.70
            )
            return results
        
        return []
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """Get statistics for a collection"""
        if collection_name not in self.vector_index:
            return {"exists": False}
        
        collection = self.vector_index[collection_name]
        
        return {
            "exists": True,
            "total_items": len(collection),
            "embedding_dimension": collection[0]["embedding"].shape[0] if collection else 0
        }
    
    def get_all_collections(self) -> List[str]:
        """Get list of all indexed collections"""
        return list(self.vector_index.keys())
    
    def clear_collection(self, collection_name: str) -> None:
        """Clear a specific collection"""
        if collection_name in self.vector_index:
            del self.vector_index[collection_name]
            print(f"[VectorSearchService] Cleared collection '{collection_name}'")
    
    def clear_all_collections(self) -> None:
        """Clear all collections"""
        self.vector_index = {}
        print(f"[VectorSearchService] Cleared all collections")


def test_vector_search():
    """Test the vector search service"""
    print("Vector Search Service Test")
    print("=" * 50)
    
    try:
        service = VectorSearchService()
        
        # Create test data
        test_items = [
            {
                "id": "uat-001",
                "title": "SQL Managed Instance deployment",
                "description": "Unable to deploy SQL MI in West Europe region. Need this service for production.",
                "metadata": {"type": "uat", "status": "open"}
            },
            {
                "id": "uat-002",
                "title": "Azure Functions deployment issue",
                "description": "Azure Functions app fails to deploy with error 'Quota exceeded'.",
                "metadata": {"type": "uat", "status": "open"}
            },
            {
                "id": "uat-003",
                "title": "SQL Database availability",
                "description": "Is Azure SQL Database available in West Europe? Need to deploy database for new project.",
                "metadata": {"type": "uat", "status": "resolved"}
            },
            {
                "id": "uat-004",
                "title": "Azure Migrate setup",
                "description": "Need help setting up Azure Migrate for SCVMM migration. Connection failing.",
                "metadata": {"type": "uat", "status": "open"}
            }
        ]
        
        # Index items
        print("\nIndexing test items...")
        count = service.index_items("test_uats", test_items)
        print(f"Indexed {count} items")
        
        # Test search 1: Similar to SQL MI
        print("\n" + "="*50)
        print("Test 1: Search for SQL Managed Instance availability")
        results = service.search(
            query="SQL Managed Instance required in Western Europe region",
            collection_name="test_uats",
            top_k=3
        )
        
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result.title} (similarity: {result.similarity:.3f})")
            print(f"   ID: {result.item_id}")
            print(f"   Description: {result.description[:80]}...")
        
        # Test search 2: Migration issue
        print("\n" + "="*50)
        print("Test 2: Search for migration problems")
        results = service.search(
            query="SCVMM migration to Azure having connection issues",
            collection_name="test_uats",
            top_k=3
        )
        
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result.title} (similarity: {result.similarity:.3f})")
            print(f"   ID: {result.item_id}")
        
        # Test search 3: Find similar issues
        print("\n" + "="*50)
        print("Test 3: Find duplicates (high similarity threshold)")
        results = service.find_similar_issues(
            title="SQL Managed Instance in West Europe",
            description="We need SQL MI available in West Europe for our production database",
            top_k=2
        )
        
        print(f"\nFound {len(results)} potential duplicates:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result.title} (similarity: {result.similarity:.3f})")
            print(f"   This might be a duplicate!")
        
        # Collection stats
        print("\n" + "="*50)
        print("Collection Statistics:")
        stats = service.get_collection_stats("test_uats")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n✓ Vector search test complete!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_vector_search()
