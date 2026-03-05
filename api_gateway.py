"""
GCS API Gateway
Central routing layer for all GCS microservices
Phase 3: API Gateway Development
"""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
import logging
import os
import uuid
import httpx
from dotenv import load_dotenv
from keyvault_config import get_keyvault_config
from config import get_app_config

# Load environment variables (non-secrets)
load_dotenv('.env.azure')

# Environment-aware app config
_app_cfg = get_app_config()

# Get secrets from Key Vault
kv_config = get_keyvault_config()
APP_INSIGHTS_CONNECTION_STRING = kv_config.get_secret('AZURE_APP_INSIGHTS_CONNECTION_STRING')

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Add Application Insights if configured
if APP_INSIGHTS_CONNECTION_STRING:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        
        # Configure Azure Monitor
        configure_azure_monitor(connection_string=APP_INSIGHTS_CONNECTION_STRING)
        logger.info("✅ Application Insights enabled - telemetry will be sent to Azure")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize Application Insights: {e}")
        logger.info("Continuing with console logging only")
else:
    logger.warning("⚠️  Application Insights not configured - using console logging only")

# Initialize FastAPI
app = FastAPI(
    title="GCS API Gateway",
    description="Global Customer Support - Unified Action Tracker API Gateway",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware — origins loaded from environment config (not a wildcard).
# Dev: localhost origins; preprod/prod: App Service hostnames.
_cors_origins = _app_cfg.cors_origins or ["*"]  # "*" only reached if config returns empty
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

# Request tracking middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with correlation ID for tracing"""
    correlation_id = str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    
    start_time = datetime.utcnow()
    
    # Log request
    client_host = request.client.host if request.client else "unknown"
    logger.info(
        "Request started",
        extra={
            "custom_dimensions": {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_host,
            }
        }
    )
    
    response = await call_next(request)
    
    # Calculate duration
    duration = (datetime.utcnow() - start_time).total_seconds()
    
    # Log response
    logger.info(
        "Request completed",
        extra={
            "custom_dimensions": {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_seconds": duration,
            }
        }
    )
    
    # Add correlation ID to response headers
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "service": "gcs-api-gateway"
    }

@app.get("/api/info")
async def api_info():
    """API information and available routes"""
    return {
        "name": "GCS API Gateway",
        "version": "1.0.0",
        "description": "Global Customer Support - Unified Action Tracker",
        "routes": {
            "search": "/api/search",
            "analyze": "/api/analyze",
            "matching": "/api/matching",
            "uat": "/api/uat",
            "context": "/api/context",
            "quality": "/api/quality",
            "ado": "/api/ado"
        },
        "status": "Phase 6 - Enhanced Matching Microservice"
    }

# Context Analysis endpoint - proxy to Context Analyzer service
@app.post("/api/context/analyze")
async def analyze_context(request: Request):
    """
    Analyze issue context via Context Analyzer microservice
    Proxies to: http://localhost:8001/analyze
    """
    try:
        # Get request body
        body = await request.json()
        
        # Forward to Context Analyzer service
        _context_url = _app_cfg.service_url(_app_cfg.context_analyzer_port)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_context_url}/analyze",
                json=body
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Context Analyzer returned error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Context Analyzer error: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to Context Analyzer: {e}")
        raise HTTPException(
            status_code=503,
            detail="Context Analyzer service unavailable"
        )
    except Exception as e:
        logger.error(f"Unexpected error in context analysis: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with logging"""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "custom_dimensions": {
                "correlation_id": correlation_id,
                "path": request.url.path,
                "error": str(exc),
                "error_type": type(exc).__name__
            }
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "correlation_id": correlation_id,
            "message": str(exc) if os.getenv('DEBUG') else "An error occurred"
        }
    )

# Import route modules
print("[DEBUG] Starting route imports...")
try:
    print("[DEBUG] Importing search, analyze, uat, context, quality, ado...")
    from gateway.routes import search, analyze, uat, context, quality, ado
    print("[DEBUG] ✅ First group imported successfully")
except Exception as e:
    print(f"[DEBUG] ❌ First group import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("[DEBUG] Importing matching...")
    from gateway.routes import matching
    print("[DEBUG] ✅ matching imported successfully")
except Exception as e:
    print(f"[DEBUG] ❌ matching import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("[DEBUG] Importing classify...")
    from gateway.routes import classify
    print("[DEBUG] ✅ classify imported successfully")
except Exception as e:
    print(f"[DEBUG] ❌ classify import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("[DEBUG] Importing embedding...")
    from gateway.routes import embedding
    print("[DEBUG] ✅ embedding imported successfully")
except Exception as e:
    print(f"[DEBUG] ❌ embedding import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    print("[DEBUG] Importing vector_search...")
    from gateway.routes import vector_search
    print("[DEBUG] ✅ vector_search imported successfully")
except Exception as e:
    print(f"[DEBUG] ❌ vector_search import failed: {e}")
    import traceback
    traceback.print_exc()

# Register route blueprints
print("[DEBUG] Starting route registrations...")
try:
    print("[DEBUG] Registering search router...")
    app.include_router(search.router, prefix="/api/search", tags=["Search"])
    print("[DEBUG] ✅ search registered")
except Exception as e:
    print(f"[DEBUG] ❌ search registration failed: {e}")

try:
    print("[DEBUG] Registering analyze router...")
    app.include_router(analyze.router, prefix="/api/analyze", tags=["Analysis"])
    print("[DEBUG] ✅ analyze registered")
except Exception as e:
    print(f"[DEBUG] ❌ analyze registration failed: {e}")

try:
    print("[DEBUG] Registering uat router...")
    app.include_router(uat.router, prefix="/api/uat", tags=["UAT Management"])
    print("[DEBUG] ✅ uat registered")
except Exception as e:
    print(f"[DEBUG] ❌ uat registration failed: {e}")

try:
    print("[DEBUG] Registering context router...")
    app.include_router(context.router, prefix="/api/context", tags=["Context"])
    print("[DEBUG] ✅ context registered")
except Exception as e:
    print(f"[DEBUG] ❌ context registration failed: {e}")

try:
    print("[DEBUG] Registering quality router...")
    app.include_router(quality.router, prefix="/api/quality", tags=["Quality"])
    print("[DEBUG] ✅ quality registered")
except Exception as e:
    print(f"[DEBUG] ❌ quality registration failed: {e}")

try:
    print("[DEBUG] Registering ado router...")
    app.include_router(ado.router, prefix="/api/ado", tags=["Azure DevOps"])
    print("[DEBUG] ✅ ado registered")
except Exception as e:
    print(f"[DEBUG] ❌ ado registration failed: {e}")

try:
    print("[DEBUG] Registering matching router...")
    app.include_router(matching.router, prefix="/api/matching", tags=["Enhanced Matching"])
    print("[DEBUG] ✅ matching registered")
except Exception as e:
    print(f"[DEBUG] ❌ matching registration failed: {e}")

try:
    print("[DEBUG] Registering classify router...")
    app.include_router(classify.router, prefix="/api/classify", tags=["LLM Classification"])
    print("[DEBUG] ✅ classify registered")
except Exception as e:
    print(f"[DEBUG] ❌ classify registration failed: {e}")

try:
    print("[DEBUG] Registering embedding router...")
    app.include_router(embedding.router, prefix="/api/embedding", tags=["Embeddings"])
    print("[DEBUG] ✅ embedding registered")
except Exception as e:
    print(f"[DEBUG] ❌ embedding registration failed: {e}")

try:
    print("[DEBUG] Registering vector_search router...")
    app.include_router(vector_search.router, prefix="/api/vector", tags=["Vector Search"])
    print("[DEBUG] ✅ vector_search registered")
except Exception as e:
    print(f"[DEBUG] ❌ vector_search registration failed: {e}")

print("[DEBUG] Route registration complete!")

if __name__ == "__main__":
    import uvicorn
    
    # Get configuration
    host = os.getenv("API_GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("API_GATEWAY_PORT", "8000"))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    logger.info(f"Starting GCS API Gateway on {host}:{port}")
    
    uvicorn.run(
        "api_gateway:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )
