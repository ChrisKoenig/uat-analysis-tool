"""
Vector Search Service - Microservice Wrapper
v1.0 - Phase 10: Microservices Transformation

Microservice for semantic similarity search using embeddings.
Provides endpoints for:
- Indexing items into collections
- Semantic similarity search
- Duplicate detection
- Collection management

Port: 8007
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import sys
import os
import logging

# Add parent directory to path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(_project_root)
sys.path.append(os.path.join(_project_root, 'apps'))

# Import Vector Search Service
from shared.vector_search import VectorSearchService, SearchResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Vector Search Service",
    description="Semantic similarity search using embeddings and cosine similarity",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class IndexItem(BaseModel):
    """Single item to index"""
    id: str
    title: str
    description: str
    metadata: Optional[Dict[str, Any]] = None

class IndexRequest(BaseModel):
    """Request to index items"""
    collection_name: str
    items: List[IndexItem]
    force_reindex: Optional[bool] = False

class SearchRequest(BaseModel):
    """Request for semantic search"""
    query: str
    collection_name: str
    top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None
    use_cache: Optional[bool] = True

class SearchContextRequest(BaseModel):
    """Request for context-based search"""
    title: str
    description: str
    collection_name: str
    top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None

class FindSimilarRequest(BaseModel):
    """Request to find similar issues/duplicates"""
    title: str
    description: str
    top_k: Optional[int] = 5

class SearchResultResponse(BaseModel):
    """Single search result"""
    item_id: str
    title: str
    description: str
    similarity: float
    metadata: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    """Response for search"""
    results: List[SearchResultResponse]
    count: int
    collection: str

class IndexResponse(BaseModel):
    """Response for indexing"""
    collection_name: str
    indexed_count: int
    success: bool

# Global service (initialized on startup)
vector_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize the vector search service on startup"""
    global vector_service
    
    logger.info("Vector Search Service starting up...")
    
    try:
        vector_service = VectorSearchService()
        logger.info("Vector Search Service initialized")
        logger.info("Embedding service ready")
    except Exception as e:
        logger.error(f"Failed to initialize Vector Search Service: {e}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    collections = vector_service.get_all_collections()
    
    return {
        "status": "healthy",
        "service": "vector-search",
        "version": "1.0.0",
        "collections": collections,
        "total_collections": len(collections)
    }

@app.get("/info")
async def service_info():
    """Service information endpoint"""
    collections_info = {}
    if vector_service:
        for collection in vector_service.get_all_collections():
            collections_info[collection] = vector_service.get_collection_stats(collection)
    
    return {
        "service": "vector-search",
        "version": "1.0.0",
        "description": "Semantic similarity search using embeddings",
        "collections": collections_info,
        "endpoints": {
            "/index": "Index items into a collection",
            "/search": "Search for similar items",
            "/search/context": "Search using title + description context",
            "/search/similar": "Find similar issues (duplicate detection)",
            "/collections": "List all collections",
            "/collections/{name}/stats": "Get collection statistics",
            "/collections/{name}": "Clear specific collection",
            "/collections/clear-all": "Clear all collections",
            "/health": "Health check",
            "/info": "Service information"
        }
    }

@app.post("/index", response_model=IndexResponse)
async def index_items(request: IndexRequest):
    """
    Index items into a collection for semantic search.
    
    Creates embeddings for each item and stores them in the named collection.
    Collections can be used to organize different types of items (e.g., "uats", "issues").
    """
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Indexing {len(request.items)} items into '{request.collection_name}'")
        
        # Convert Pydantic models to dicts
        items_dict = [item.dict() for item in request.items]
        
        count = vector_service.index_items(
            collection_name=request.collection_name,
            items=items_dict,
            force_reindex=request.force_reindex
        )
        
        logger.info(f"Successfully indexed {count} items")
        
        return IndexResponse(
            collection_name=request.collection_name,
            indexed_count=count,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Indexing error: {e}")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Perform semantic similarity search.
    
    Searches for items most similar to the query text using cosine similarity
    of embeddings. Returns results above the similarity threshold, ordered by
    similarity (highest first).
    """
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Searching '{request.collection_name}': {request.query[:50]}...")
        
        results = vector_service.search(
            query=request.query,
            collection_name=request.collection_name,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
            use_cache=request.use_cache
        )
        
        logger.info(f"Found {len(results)} results")
        
        # Convert to response format
        result_responses = [
            SearchResultResponse(
                item_id=r.item_id,
                title=r.title,
                description=r.description,
                similarity=r.similarity,
                metadata=r.metadata
            )
            for r in results
        ]
        
        return SearchResponse(
            results=result_responses,
            count=len(result_responses),
            collection=request.collection_name
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/search/context", response_model=SearchResponse)
async def search_with_context(request: SearchContextRequest):
    """
    Search using title + description context.
    
    Combines title and description into a single query for semantic search.
    Useful when you have structured input rather than a single query string.
    """
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Context search in '{request.collection_name}': {request.title[:50]}...")
        
        results = vector_service.search_with_context(
            title=request.title,
            description=request.description,
            collection_name=request.collection_name,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        logger.info(f"Found {len(results)} results")
        
        result_responses = [
            SearchResultResponse(
                item_id=r.item_id,
                title=r.title,
                description=r.description,
                similarity=r.similarity,
                metadata=r.metadata
            )
            for r in results
        ]
        
        return SearchResponse(
            results=result_responses,
            count=len(result_responses),
            collection=request.collection_name
        )
        
    except Exception as e:
        logger.error(f"Context search error: {e}")
        raise HTTPException(status_code=500, detail=f"Context search failed: {str(e)}")

@app.post("/search/similar", response_model=SearchResponse)
async def find_similar_issues(request: FindSimilarRequest):
    """
    Find similar issues for duplicate detection.
    
    Uses higher similarity threshold (0.70) to find potential duplicates.
    Searches across available collections (UATs, issues) to find matches.
    """
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Finding similar issues: {request.title[:50]}...")
        
        results = vector_service.find_similar_issues(
            title=request.title,
            description=request.description,
            top_k=request.top_k
        )
        
        logger.info(f"Found {len(results)} potential duplicates")
        
        result_responses = [
            SearchResultResponse(
                item_id=r.item_id,
                title=r.title,
                description=r.description,
                similarity=r.similarity,
                metadata=r.metadata
            )
            for r in results
        ]
        
        return SearchResponse(
            results=result_responses,
            count=len(result_responses),
            collection="multiple"  # Searches multiple collections
        )
        
    except Exception as e:
        logger.error(f"Similar issues search error: {e}")
        raise HTTPException(status_code=500, detail=f"Similar issues search failed: {str(e)}")

@app.get("/collections")
async def list_collections():
    """
    List all indexed collections.
    
    Returns names of all available collections that have been indexed.
    """
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        collections = vector_service.get_all_collections()
        
        return {
            "collections": collections,
            "count": len(collections)
        }
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/collections/{collection_name}/stats")
async def get_collection_stats(collection_name: str):
    """
    Get statistics for a specific collection.
    
    Returns information about the collection including total items and dimensions.
    """
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        stats = vector_service.get_collection_stats(collection_name)
        
        if not stats.get("exists", False):
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/collections/{collection_name}")
async def clear_collection(collection_name: str):
    """
    Clear a specific collection.
    
    Removes all items from the named collection. The collection can be
    re-indexed with new items later.
    """
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        vector_service.clear_collection(collection_name)
        logger.info(f"Cleared collection '{collection_name}'")
        
        return {
            "success": True,
            "message": f"Collection '{collection_name}' cleared"
        }
    except Exception as e:
        logger.error(f"Error clearing collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collections/clear-all")
async def clear_all_collections():
    """
    Clear all collections.
    
    Removes all items from all collections. Use with caution!
    """
    if vector_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        vector_service.clear_all_collections()
        logger.info("Cleared all collections")
        
        return {
            "success": True,
            "message": "All collections cleared"
        }
    except Exception as e:
        logger.error(f"Error clearing all collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("Vector Search Service - Starting")
    print("="*80)
    print(f"Port: 8007")
    print(f"Features: Semantic Search, Duplicate Detection, Collection Management")
    print(f"Algorithm: Cosine Similarity on Embeddings")
    print(f"Operations: Index, Search, Find Similar, Manage Collections")
    print("="*80)
    
    uvicorn.run(app, host="0.0.0.0", port=8007)
