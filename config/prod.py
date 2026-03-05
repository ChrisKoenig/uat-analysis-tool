"""
Production environment configuration
======================================
Production Azure deployment.

All sensitive identifiers are read from environment variables (set as App
Service application settings / container env vars).  This file intentionally
contains NO hard-coded resource names or subscription IDs.

To activate:  set APP_ENV=prod
Required env vars — the app will fail fast if any are missing:
  AZURE_TENANT_ID
  AZURE_SUBSCRIPTION_ID
  RESOURCE_GROUP
  KEY_VAULT_NAME
  COSMOS_ACCOUNT
  OPENAI_ACCOUNT
  ADO_ORGANIZATION
  ADO_PROJECT
"""

import os
from config import AppConfig


def _require(var: str) -> str:
    """Read a required env var; raise immediately if absent."""
    val = os.environ.get(var)
    if not val:
        raise EnvironmentError(
            f"[config/prod] Required environment variable '{var}' is not set. "
            "Set it in the App Service application settings or container environment."
        )
    return val


PROD_CONFIG = AppConfig(
    app_env="prod",

    # ── Identity ──────────────────────────────────────────────────────────────
    tenant_id=_require("AZURE_TENANT_ID"),
    subscription_id=_require("AZURE_SUBSCRIPTION_ID"),
    resource_group=_require("RESOURCE_GROUP"),

    # ── Key Vault ─────────────────────────────────────────────────────────────
    key_vault_name=_require("KEY_VAULT_NAME"),

    # ── Cosmos DB ─────────────────────────────────────────────────────────────
    cosmos_account=_require("COSMOS_ACCOUNT"),
    cosmos_database=os.environ.get("COSMOS_DATABASE", "triage-management"),

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    openai_account=_require("OPENAI_ACCOUNT"),
    openai_api_version=os.environ.get("OPENAI_API_VERSION", "2024-08-01-preview"),
    embedding_model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
    classification_model=os.environ.get("OPENAI_CLASSIFICATION_MODEL", "gpt-4o"),
    embedding_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large"),
    classification_deployment=os.environ.get("AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT", "gpt-4o-standard"),

    # ── Azure Storage ─────────────────────────────────────────────────────────
    storage_account=_require("STORAGE_ACCOUNT"),
    storage_container=os.environ.get("STORAGE_CONTAINER", "gcs-data"),

    # ── Azure DevOps ──────────────────────────────────────────────────────────
    ado_organization=_require("ADO_ORGANIZATION"),
    ado_project=_require("ADO_PROJECT"),
    ado_tft_organization=os.environ.get("ADO_TFT_ORGANIZATION", "acrblockers"),
    ado_tft_project=os.environ.get("ADO_TFT_PROJECT", "Technical Feedback"),
    microsoft_tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",

    # ── Managed Identity ──────────────────────────────────────────────────────
    managed_identity_name=os.environ.get("MANAGED_IDENTITY_NAME", ""),
    managed_identity_client_id=os.environ.get("AZURE_CLIENT_ID", ""),

    # ── Microservice ports ────────────────────────────────────────────────────
    api_gateway_port=int(os.environ.get("API_GATEWAY_PORT", "8000")),
    context_analyzer_port=int(os.environ.get("CONTEXT_ANALYZER_PORT", "8001")),
    search_service_port=int(os.environ.get("SEARCH_SERVICE_PORT", "8002")),
    enhanced_matching_port=int(os.environ.get("ENHANCED_MATCHING_PORT", "8003")),
    uat_management_port=int(os.environ.get("UAT_MANAGEMENT_PORT", "8004")),
    llm_classifier_port=int(os.environ.get("LLM_CLASSIFIER_PORT", "8005")),
    embedding_service_port=int(os.environ.get("EMBEDDING_SERVICE_PORT", "8006")),
    vector_search_port=int(os.environ.get("VECTOR_SEARCH_PORT", "8007")),
    admin_service_port=int(os.environ.get("ADMIN_SERVICE_PORT", "8008")),
    triage_api_port=int(os.environ.get("TRIAGE_API_PORT", "8009")),
    triage_ui_port=int(os.environ.get("TRIAGE_UI_PORT", "3000")),
    field_api_port=int(os.environ.get("FIELD_API_PORT", "8010")),
    field_ui_port=int(os.environ.get("FIELD_UI_PORT", "3001")),
    main_app_port=int(os.environ.get("MAIN_APP_PORT", "5003")),

    # ── App behaviour ─────────────────────────────────────────────────────────
    debug=False,                                      # NEVER true in prod
    log_level=os.environ.get("LOG_LEVEL", "WARNING"),
    cors_origins=os.environ.get("CORS_ORIGINS", "").split(",") if os.environ.get("CORS_ORIGINS") else [],

    # ── Azure region ──────────────────────────────────────────────────────────
    azure_location=os.environ.get("AZURE_LOCATION", "northcentralus"),
)
