"""
Embedding Service - Microservice Wrapper
v1.0 - Phase 9: Microservices Transformation

Microservice for generating text embeddings using Azure OpenAI.
Provides endpoints for:
- Single text embedding
- Batch text embedding
- Context embedding (title + description + impact)
- Cosine similarity calculation
- Cache management

Port: 8006
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import sys
import os
import logging
import numpy as np

# Add parent directory to path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(_project_root)
sys.path.append(os.path.join(_project_root, 'apps'))

# Import Embedding Service
from shared.embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service (initialized on startup)
embedding_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup the embedding service"""
    global embedding_service
    
    # Startup
    logger.info("Embedding Service starting up...")
    try:
        embedding_service = EmbeddingService()
        logger.info("Embedding Service initialized")
        logger.info("Azure OpenAI integration ready")
    except Exception as e:
        logger.error(f"Failed to initialize Embedding Service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Embedding Service shutting down...")

app = FastAPI(
    title="Embedding Service",
    description="Text embedding generation using Azure OpenAI with smart caching",
    version="1.0.0",
    lifespan=lifespan
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
class EmbedRequest(BaseModel):
    """Request for single text embedding"""
    text: str
    use_cache: Optional[bool] = True

class EmbedBatchRequest(BaseModel):
    """Request for batch embedding"""
    texts: List[str]
    use_cache: Optional[bool] = True

class EmbedContextRequest(BaseModel):
    """Request for context embedding"""
    title: str
    description: str
    impact: Optional[str] = None
    use_cache: Optional[bool] = True

class SimilarityRequest(BaseModel):
    """Request for similarity calculation"""
    embedding1: List[float]
    embedding2: List[float]

class EmbedResponse(BaseModel):
    """Response for single embedding"""
    embedding: List[float]
    dimension: int
    cached: bool = False

class EmbedBatchResponse(BaseModel):
    """Response for batch embedding"""
    embeddings: List[List[float]]
    count: int
    dimension: int

class EmbedContextResponse(BaseModel):
    """Response for context embedding"""
    title_embedding: List[float]
    description_embedding: List[float]
    impact_embedding: Optional[List[float]] = None
    combined_embedding: List[float]
    dimension: int

class SimilarityResponse(BaseModel):
    """Response for similarity calculation"""
    similarity: float

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "status": "healthy",
        "service": "embedding",
        "model": "text-embedding-3-large"
    }

@app.get("/info")
async def health_check():
    """Health check endpoint"""
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "status": "healthy",
        "service": "embedding-service",
        "version": "1.0.0",
        "model": embedding_service.model,
        "deployment": embedding_service.deployment
    }

@app.get("/info")
async def service_info():
    """Service information endpoint"""
    return {
        "service": "embedding-service",
        "version": "1.0.0",
        "description": "Text embedding generation using Azure OpenAI",
        "model": embedding_service.model if embedding_service else "not initialized",
        "deployment": embedding_service.deployment if embedding_service else "not initialized",
        "dimension": 3072,  # text-embedding-3-large
        "endpoints": {
            "/embed": "Generate single text embedding",
            "/embed/batch": "Generate embeddings for multiple texts",
            "/embed/context": "Generate embeddings for context (title + description + impact)",
            "/similarity": "Calculate cosine similarity between embeddings",
            "/cache/stats": "Get cache statistics",
            "/cache/clear": "Clear cache",
            "/health": "Health check",
            "/info": "Service information"
        }
    }

@app.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    """
    Generate embedding for a single text.
    
    Uses Azure OpenAI text-embedding-3-large model with smart caching.
    Returns 3072-dimensional embedding vector.
    """
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Embedding text: {request.text[:50]}...")
        
        embedding = embedding_service.embed(
            text=request.text,
            use_cache=request.use_cache
        )
        
        return EmbedResponse(
            embedding=embedding.tolist(),
            dimension=len(embedding),
            cached=False  # Cache info not directly available
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")

@app.post("/embed/batch", response_model=EmbedBatchResponse)
async def embed_batch(request: EmbedBatchRequest):
    """
    Generate embeddings for multiple texts in batch.
    
    Efficiently processes multiple texts with caching support.
    Returns list of embedding vectors.
    """
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Batch embedding {len(request.texts)} texts...")
        
        embeddings = embedding_service.embed_batch(
            texts=request.texts,
            use_cache=request.use_cache
        )
        
        # Convert numpy arrays to lists
        embeddings_list = [emb.tolist() for emb in embeddings]
        
        logger.info(f"Batch embedding complete: {len(embeddings_list)} embeddings")
        
        return EmbedBatchResponse(
            embeddings=embeddings_list,
            count=len(embeddings_list),
            dimension=len(embeddings_list[0]) if embeddings_list else 0
        )
        
    except Exception as e:
        logger.error(f"Batch embedding error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch embedding failed: {str(e)}")

@app.post("/embed/context", response_model=EmbedContextResponse)
async def embed_context(request: EmbedContextRequest):
    """
    Generate embeddings for a context (title + description + impact).
    
    Creates separate embeddings for each component and a weighted combined embedding:
    - Title: Weight 2.0 (most important)
    - Description: Weight 1.0
    - Impact: Weight 0.5 (if provided)
    
    Returns all embeddings plus the combined one for similarity matching.
    """
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        logger.info(f"Embedding context: {request.title[:50]}...")
        
        result = embedding_service.embed_context(
            title=request.title,
            description=request.description,
            impact=request.impact,
            use_cache=request.use_cache
        )
        
        response = EmbedContextResponse(
            title_embedding=result["title_embedding"].tolist(),
            description_embedding=result["description_embedding"].tolist(),
            combined_embedding=result["combined_embedding"].tolist(),
            dimension=len(result["combined_embedding"])
        )
        
        if "impact_embedding" in result:
            response.impact_embedding = result["impact_embedding"].tolist()
        
        logger.info("Context embedding complete")
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Context embedding error: {e}")
        raise HTTPException(status_code=500, detail=f"Context embedding failed: {str(e)}")

@app.post("/similarity", response_model=SimilarityResponse)
async def calculate_similarity(request: SimilarityRequest):
    """
    Calculate cosine similarity between two embeddings.
    
    Returns similarity score between 0 and 1:
    - 1.0: Identical embeddings
    - 0.0: Orthogonal embeddings
    - Higher values indicate more semantic similarity
    """
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Convert lists to numpy arrays
        emb1 = np.array(request.embedding1)
        emb2 = np.array(request.embedding2)
        
        # Validate dimensions match
        if len(emb1) != len(emb2):
            raise ValueError(f"Embedding dimensions don't match: {len(emb1)} vs {len(emb2)}")
        
        similarity = embedding_service.cosine_similarity(emb1, emb2)
        
        return SimilarityResponse(similarity=float(similarity))
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Similarity calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Similarity calculation failed: {str(e)}")

@app.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics.
    
    Returns information about cache usage, hit rates, and performance.
    """
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        stats = embedding_service.get_cache_stats()
        return {
            "cache_enabled": True,
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/clear")
async def clear_cache():
    """
    Clear embedding cache.
    
    Removes all cached embeddings. Useful for forcing fresh embeddings
    or clearing outdated cache entries.
    """
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        embedding_service.clear_cache()
        logger.info("Cache cleared successfully")
        return {
            "success": True,
            "message": "Embedding cache cleared"
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/cleanup")
async def cleanup_cache():
    """
    Clean up expired cache entries.
    
    Removes cache entries that have exceeded the TTL (time-to-live).
    Returns the number of entries cleaned up.
    """
    if embedding_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        count = embedding_service.cleanup_expired_cache()
        logger.info(f"Cache cleanup removed {count} expired entries")
        return {
            "success": True,
            "removed_count": count,
            "message": f"Cleaned up {count} expired cache entries"
        }
    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("Embedding Service - Starting")
    print("="*80)
    print(f"Port: 8006")
    print(f"Features: Azure OpenAI Embeddings, Smart Caching, Batch Processing")
    print(f"Model: text-embedding-3-large (3072 dimensions)")
    print(f"Operations: Embed, Batch Embed, Context Embed, Similarity")
    print("="*80)
    
    uvicorn.run(app, host="0.0.0.0", port=8006)
