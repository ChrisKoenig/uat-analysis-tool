"""
Dev environment configuration
==============================
Local developer workstation settings.

Subscription:   13267e8e-b8f0-41c3-ba3e-509b3c7c8482  (GCS Dev)
Tenant:         16b3c013-d300-468d-ac64-7eda0820b6d3  (GCS / FDPO)
Key Vault:      kv-gcs-dev-gg4a6y
Cosmos DB:      cosmos-gcs-dev
Azure OpenAI:   OpenAI-bp-NorthCentral  (deployment: gpt-4o-02)

To activate:  set APP_ENV=dev   (or omit APP_ENV entirely — dev is the default)
"""

from config import AppConfig

DEV_CONFIG = AppConfig(
    app_env="dev",

    # ── Identity ──────────────────────────────────────────────────────────────
    tenant_id="16b3c013-d300-468d-ac64-7eda0820b6d3",
    subscription_id="13267e8e-b8f0-41c3-ba3e-509b3c7c8482",
    resource_group="rg-gcs-dev",

    # ── Key Vault ─────────────────────────────────────────────────────────────
    key_vault_name="kv-gcs-dev-gg4a6y",

    # ── Cosmos DB ─────────────────────────────────────────────────────────────
    cosmos_account="cosmos-gcs-dev",
    cosmos_database="triage-management",

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    openai_account="OpenAI-bp-NorthCentral",
    openai_api_version="2024-08-01-preview",
    embedding_model="text-embedding-3-large",
    classification_model="gpt-4o",
    embedding_deployment="text-embedding-3-large",
    classification_deployment="gpt-4o-02",          # dev-specific deployment name

    # ── Azure Storage ─────────────────────────────────────────────────────────
    storage_account="stgcsdevgg4a6y",
    storage_container="gcs-data",

    # ── Azure DevOps ──────────────────────────────────────────────────────────
    ado_organization="unifiedactiontrackertest",
    ado_project="Unified Action Tracker Test",
    ado_tft_organization="unifiedactiontracker",
    ado_tft_project="Technical Feedback",
    microsoft_tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",

    # ── Managed Identity ──────────────────────────────────────────────────────
    managed_identity_name="mi-gcs-dev",

    # ── Container / ACR ───────────────────────────────────────────────────────
    acr_name="acrgcsdevgg4a6y",
    container_env_name="cae-gcs-dev",

    # ── Microservice ports (defaults are fine for dev) ────────────────────────
    api_gateway_port=8000,
    context_analyzer_port=8001,
    search_service_port=8002,
    enhanced_matching_port=8003,
    uat_management_port=8004,
    llm_classifier_port=8005,
    embedding_service_port=8006,
    vector_search_port=8007,
    admin_service_port=8008,
    triage_api_port=8009,
    triage_ui_port=3000,
    field_api_port=8010,
    field_ui_port=3001,
    main_app_port=5003,

    # ── App behaviour ─────────────────────────────────────────────────────────
    debug=True,
    log_level="DEBUG",
    cors_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5003",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5003",
    ],

    # ── Azure region ──────────────────────────────────────────────────────────
    azure_location="northcentralus",
)
