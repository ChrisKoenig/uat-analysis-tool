"""
Field Portal API — FastAPI Application Entry Point

Runs on port 8010. Orchestrates the 9-step field submission flow
by calling existing microservices via the API Gateway (:8000).

Start with:
    python -m uvicorn field-portal.api.main:app --host 0.0.0.0 --port 8010 --reload

Or via the desktop launcher (launcher.py).
"""

import logging
import os
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

# ── Application Insights telemetry ──
try:
    _ai_conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if _ai_conn:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=_ai_conn)
        # Suppress verbose Azure SDK HTTP logging (full request/response headers)
        # Telemetry still flows to App Insights — just not to the console.
        for _name in (
            "azure.core.pipeline.policies.http_logging_policy",
            "azure.monitor.opentelemetry.exporter",
            "azure.monitor.opentelemetry.exporter.export",
            "azure.monitor.opentelemetry.exporter.export._base",
            "azure.identity",
            "azure.identity._credentials",
        ):
            logging.getLogger(_name).setLevel(logging.WARNING)
        logger.info("Application Insights enabled for Field Portal API")
except Exception as _ai_err:
    logger.warning("App Insights init skipped: %s", _ai_err)


# ── Lifespan (startup / shutdown) ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    import sys, os, time as _t

    def _log(msg: str):
        """Timestamped debug log — prints + logs so Azure log stream captures it."""
        ts = f"{_t.time():.3f}"
        line = f"[STARTUP {ts}] {msg}"
        print(line, flush=True)
        logger.info(msg)

    _log(f"Field Portal API starting on port {FIELD_PORTAL_PORT}")
    _log(f"  PID={os.getpid()}  Python={sys.version}")
    _log(f"  KEY_VAULT_NAME={os.environ.get('KEY_VAULT_NAME', '(not set)')}")
    _log(f"  AZURE_CLIENT_ID={os.environ.get('AZURE_CLIENT_ID', '(not set)')}")
    _log(f"  API_GATEWAY_URL={os.environ.get('API_GATEWAY_URL', '(not set)')}")
    _log(f"  WEBSITES_PORT={os.environ.get('WEBSITES_PORT', '(not set)')}")
    _log(f"  PORT={os.environ.get('PORT', '(not set)')}")

    # Pre-load KeyVault config + shared credential at startup so the
    # first user request doesn't pay ~30s of credential chain timeouts.
    try:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            sys.path.insert(0, os.path.join(project_root, 'apps'))
        _log(f"  project_root added to sys.path: {project_root}")

        # 0. Quick network check — is KeyVault reachable?
        _log("Step 0: KeyVault TCP reachability check (3s timeout)...")
        _t0 = _t.time()
        from shared.keyvault_config import check_reachable as _kv_check
        kv_ok, kv_msg = _kv_check(timeout_seconds=3.0)
        _log(f"Step 0 done in {_t.time()-_t0:.1f}s — reachable={kv_ok}")
        if kv_ok:
            _log(f"  ✅ {kv_msg}")
        else:
            _log(f"  ⚠️ {kv_msg}")

        # 1. Pre-load KeyVault secrets (triggers credential + secret reads)
        _log("Step 1: Loading AI config (KeyVault secrets)...")
        _t0 = _t.time()
        from shared.ai_config import get_config as get_ai_config
        _cfg = get_ai_config()
        _log(f"Step 1 done in {_t.time()-_t0:.1f}s  (endpoint={'set' if _cfg.azure_openai.endpoint else 'MISSING'})")

        # 2. Pre-warm shared credential (background thread — non-blocking)
        _log("Step 2: Starting shared_auth warm_up (background thread)...")
        _t0 = _t.time()
        from shared.shared_auth import warm_up
        warm_up()
        _log(f"Step 2 dispatched in {_t.time()-_t0:.1f}s (thread is running in background)")
    except Exception as e:
        _log(f"⚠️ Startup pre-load FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # 3. Gateway health check (also wrapped in try/except so it never blocks startup)
    try:
        _log("Step 3: Checking gateway connectivity...")
        _t0 = _t.time()
        gw = get_gateway()
        _log(f"  Gateway URL: {gw.base_url}")
        reachable = await gw.check_health()
        _log(f"Step 3 done in {_t.time()-_t0:.1f}s — reachable={reachable}")
        if reachable:
            _log("  ✅ API Gateway is reachable")
        else:
            _log("  ⚠️  API Gateway not reachable — some features will fail")
    except Exception as e:
        _log(f"  ⚠️ Gateway check FAILED: {type(e).__name__}: {e}")

    _log("=== Startup sequence complete — yielding to app ===")
    yield
    # Shutdown
    try:
        gw = get_gateway()
        await gw.close()
    except Exception:
        pass
    _log("Field Portal API shut down")


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


# ── Health endpoint (root level for App Service probe) ──
@app.get("/health", tags=["Meta"])
async def root_health():
    """Root-level health endpoint for App Service health probes.

    Delegates to the detailed /api/field/health endpoint on the router.
    This avoids duplicating health logic while giving App Service a
    simple top-level URL to probe.
    """
    import time as _t
    _t0 = _t.time()
    status = "ok"
    components = {}

    # Gateway reachability
    try:
        gw = get_gateway()
        gw_ok = await gw.check_health()
        components["gateway"] = "ok" if gw_ok else "degraded"
        if not gw_ok:
            status = "degraded"
    except Exception:
        components["gateway"] = "degraded"
        status = "degraded"

    # KeyVault
    try:
        from keyvault_config import check_reachable
        kv_ok, _ = check_reachable(timeout_seconds=2.0)
        components["key_vault"] = "ok" if kv_ok else "degraded"
    except Exception:
        components["key_vault"] = "unknown"

    # AI config
    try:
        from shared.ai_config import get_config as _get_ai
        cfg = _get_ai()
        components["ai"] = "ok" if cfg.azure_openai.endpoint else "degraded"
    except Exception:
        components["ai"] = "degraded"

    return {
        "service": "Field Portal API",
        "status": status,
        "components": components,
        "response_time_ms": round((_t.time() - _t0) * 1000),
    }


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
