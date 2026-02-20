"""
Field Portal API — FastAPI Application Entry Point

Runs on port 8010. Orchestrates the 9-step field submission flow
by calling existing microservices via the API Gateway (:8000).

Start with:
    python -m uvicorn field-portal.api.main:app --host 0.0.0.0 --port 8010 --reload

Or via the desktop launcher (launcher.py).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS, FIELD_PORTAL_PORT
from .routes import router
from .gateway_client import get_gateway

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("field-portal")


# ── Lifespan (startup / shutdown) ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Field Portal API starting on port {FIELD_PORTAL_PORT}")

    # Pre-load KeyVault config + shared credential at startup so the
    # first user request doesn't pay ~30s of credential chain timeouts.
    try:
        import sys, os, time as _t
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        # 0. Quick network check — is KeyVault reachable?
        #    TODO: REMOVE this block before pre-prod (vault always reachable there)
        from keyvault_config import check_reachable as _kv_check
        kv_ok, kv_msg = _kv_check(timeout_seconds=3.0)
        if kv_ok:
            logger.info(f"✅ {kv_msg}")
        else:
            logger.warning(kv_msg)
            print(kv_msg)  # make sure it's visible in the terminal

        # 1. Pre-load KeyVault secrets (triggers DefaultAzureCredential once)
        _t0 = _t.time()
        from ai_config import get_config as get_ai_config
        _cfg = get_ai_config()
        logger.info(f"AI config loaded in {_t.time()-_t0:.1f}s  (endpoint={'set' if _cfg.azure_openai.endpoint else 'MISSING'})")

        # 2. Pre-warm shared credential (background thread — non-blocking)
        from shared_auth import warm_up
        warm_up()
    except Exception as e:
        logger.warning(f"Startup pre-load failed (will initialise on first request): {e}")

    logger.info("Checking gateway connectivity...")
    gw = get_gateway()
    reachable = await gw.check_health()
    if reachable:
        logger.info("✅ API Gateway is reachable")
    else:
        logger.warning("⚠️  API Gateway not reachable — some features will fail")
    yield
    # Shutdown
    await gw.close()
    logger.info("Field Portal API shut down")


# ── FastAPI App ──
app = FastAPI(
    title="Field Portal API",
    description=(
        "REST API for the field submission portal. Orchestrates the 9-step "
        "issue submission flow (submit → quality → analysis → correction → "
        "search → UAT input → related UATs → UAT selection → UAT creation). "
        "Calls existing microservices via the API Gateway."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──
app.include_router(router)


# ── Root endpoint ──
@app.get("/", tags=["Meta"])
async def root():
    return {
        "service": "Field Portal API",
        "version": "1.0.0",
        "docs": "/docs",
        "flow_endpoints": [
            "POST /api/field/submit",
            "POST /api/field/analyze/{session_id}",
            "POST /api/field/correct",
            "POST /api/field/search/{session_id}",
            "POST /api/field/features/toggle",
            "POST /api/field/uat-input",
            "POST /api/field/related-uats/{session_id}",
            "POST /api/field/uats/toggle",
            "POST /api/field/create-uat",
            "GET  /api/field/session/{session_id}",
            "GET  /api/field/health",
        ],
    }
