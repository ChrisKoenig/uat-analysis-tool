"""
Field Portal API — Configuration Constants

Central configuration for the React SPA backend (FastAPI on port 8010).
All values can be overridden via environment variables where noted.

Architecture:
  React UI (Vite, :3001)  →  This API (:8010)  →  Microservice Gateway (:8000)
                                                →  ADO integration (direct)
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
FIELD_PORTAL_PORT = int(os.environ.get("FIELD_PORTAL_PORT", "8010"))
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

# Test org (UAT work items are created here).
ADO_TEST_ORG = "unifiedactiontrackertest"
# Production org (TFT features live here — read-only search).
ADO_PROD_ORG = "unifiedactiontracker"


# ============================================================================
# CORS (React UI)
# ============================================================================

# Allowed origins for the Vite dev server. In production these would be
# replaced by the deployed SPA domain.
CORS_ORIGINS = [
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
