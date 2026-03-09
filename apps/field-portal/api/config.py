"""
Field Portal API — Configuration Constants

Central configuration for the React SPA backend (FastAPI on port 8000).
All values can be overridden via environment variables where noted.

Architecture (local dev):
  React UI (Vite, :3001)  →  This API (:8000)  →  Microservice Gateway (triage-api)
                                                →  ADO integration (direct)

Architecture (App Service):
  field-ui (pm2+serve)  →  field-api (gunicorn+uvicorn)  →  triage-api (gateway)
                                                          →  ADO (Managed Identity)
                                                          →  Cosmos DB (MI)
"""
import os

# ============================================================================
# Service Endpoints
# ============================================================================

# Base URL of the existing microservice gateway (quality, context analysis,
# search, embeddings, vector search). The gateway aggregates the older
# Flask-based microservices that predate this React/FastAPI rewrite.
API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL", "http://localhost:8000")

# Host and port for THIS FastAPI service (field-portal backend).
# Default 8000 matches App Service WEBSITES_PORT; local dev can override.
FIELD_PORTAL_PORT = int(os.environ.get("FIELD_PORTAL_PORT", os.environ.get("PORT", "8000")))
FIELD_PORTAL_HOST = os.environ.get("FIELD_PORTAL_HOST", "0.0.0.0")


# ============================================================================
# Session Management
# ============================================================================

# In-memory session TTL in seconds. Sessions older than this are garbage-
# collected by the background cleanup thread in session_manager.py.
TEMP_STORAGE_TTL = 3600  # 1 hour


# ============================================================================
# Quality Evaluation (Step 2)
# ============================================================================

# A submission with a quality score below BLOCK is rejected outright.
QUALITY_BLOCK_THRESHOLD = 50   # score < 50 → blocks submission
# A score between BLOCK and WARN shows a "could be improved" banner.
QUALITY_WARN_THRESHOLD = 80    # score < 80 → shows improvement warning


# ============================================================================
# UAT & Feature Search (Steps 5-8)
# ============================================================================

# How far back to look for similar UATs in Azure DevOps (days).
UAT_SEARCH_DAYS = 180
# Maximum number of related UATs a user can link to their new work item.
UAT_MAX_SELECTED = 5
# Cosine-similarity threshold for TFT Feature matches (0.0-1.0).
# Features below this score are filtered out of search results.
TFT_SIMILARITY_THRESHOLD = 0.6


# ============================================================================
# Azure DevOps Organizations
# ============================================================================

# Resolve from active environment config; fall back to known dev values.
def _load_ado_orgs() -> tuple[str, str]:
    org = os.environ.get("ADO_ORGANIZATION")
    tft = os.environ.get("ADO_TFT_ORGANIZATION")
    if org and tft:
        return org, tft
    try:
        from shared.config import get_app_config
        c = get_app_config()
        return c.ado_organization, c.ado_tft_organization
    except Exception:
        return "unifiedactiontrackertest", "unifiedactiontracker"

ADO_TEST_ORG, ADO_PROD_ORG = _load_ado_orgs()


# ============================================================================
# CORS (React UI)
# ============================================================================

# Resolve allowed origins from environment config.
def _load_cors_origins() -> list:
    # Allow explicit override via env var (comma-separated)
    env_origins = os.environ.get("CORS_ORIGINS")
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    try:
        from shared.config import get_app_config
        origins = get_app_config().cors_origins
        if origins:
            return origins
    except Exception:
        pass
    # Fallback: localhost dev origins
    return ["http://localhost:3001", "http://127.0.0.1:3001"]

CORS_ORIGINS = _load_cors_origins()
