"""
Triage Service Entry Point
============================

Starts the Triage Management API on port 8009.

Usage:
    python -m triage.triage_service          # Direct run
    uvicorn triage.triage_service:app --port 8009  # Via uvicorn

This module:
    1. Re-exports the FastAPI app from the API routes module
    2. Provides the uvicorn startup when run directly
    3. Follows the same pattern as other microservices in the project
"""

import logging
import uvicorn

from triage.api.routes import app
from triage.config.logging_config import setup_logging


# =============================================================================
# Logging Configuration
# =============================================================================

# Centralized setup — configures all triage.* loggers at once.
# Override level with TRIAGE_LOG_LEVEL env var (DEBUG for full trace).
setup_logging()

logger = logging.getLogger("triage-service")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Triage Management API starting on port 8009")
    logger.info("Docs:   http://localhost:8009/docs")
    logger.info("ReDoc:  http://localhost:8009/redoc")
    logger.info("Health: http://localhost:8009/health")
    logger.info("=" * 60)
    
    uvicorn.run(
        "triage.triage_service:app",
        host="0.0.0.0",
        port=8009,
        reload=True,  # Auto-reload for development
        log_level="info",
    )
