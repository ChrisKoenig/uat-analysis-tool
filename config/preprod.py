"""
Pre-prod environment configuration
====================================
Non-production Azure App Service deployment.

Subscription:   a1e66643-8021-4548-8e36-f08076057b6a  (nonprod)
Tenant:         16b3c013-d300-468d-ac64-7eda0820b6d3  (GCS / FDPO)
Key Vault:      kv-aitriage
Cosmos DB:      cosmos-aitriage-nonprod
Azure OpenAI:   openai-aitriage-nonprod  (deployment: gpt-4o-standard)

To activate:  set APP_ENV=preprod
"""

from config import AppConfig

PREPROD_CONFIG = AppConfig(
    app_env="preprod",

    # ── Identity ──────────────────────────────────────────────────────────────
    tenant_id="16b3c013-d300-468d-ac64-7eda0820b6d3",
    subscription_id="a1e66643-8021-4548-8e36-f08076057b6a",
    resource_group="rg-nonprod-aitriage",

    # ── Key Vault ─────────────────────────────────────────────────────────────
    key_vault_name="kv-aitriage",

    # ── Cosmos DB ─────────────────────────────────────────────────────────────
    cosmos_account="cosmos-aitriage-nonprod",
    cosmos_database="triage-management",

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    openai_account="openai-aitriage-nonprod",
    openai_api_version="2024-08-01-preview",
    embedding_model="text-embedding-3-large",
    classification_model="gpt-4o",
    embedding_deployment="text-embedding-3-large",
    classification_deployment="gpt-4o-standard",

    # ── Azure Storage ─────────────────────────────────────────────────────────
    storage_account="",                               # set STORAGE_ACCOUNT env var
    storage_container="gcs-data",

    # ── Azure DevOps ──────────────────────────────────────────────────────────
    ado_organization="unifiedactiontrackertest",
    ado_project="Unified Action Tracker Test",
    ado_tft_organization="acrblockers",
    ado_tft_project="Technical Feedback",
    microsoft_tenant_id="72f988bf-86f1-41af-91ab-2d7cd011db47",

    # ── Managed Identity ──────────────────────────────────────────────────────
    managed_identity_name="TechRoB-Automation-DEV",
    managed_identity_client_id="0fe9d340-a359-4849-8c0f-d3c9640017ee",
    managed_identity_object_id="309baa86-f939-4fc3-ab3e-e2d3d0d4e475",

    # ── App Service names (used by deployment scripts) ────────────────────────
    # Stored here for reference; deploy scripts read them from this module.
    acr_name="",                                      # set ACR_NAME env var
    container_env_name="",

    # ── Microservice ports (same as dev — services run on App Service workers) ─
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
    debug=False,
    log_level="INFO",
    cors_origins=[
        "https://app-triage-ui-nonprod.azurewebsites.net",
        "https://app-triage-api-nonprod.azurewebsites.net",
        "https://app-field-ui-nonprod.azurewebsites.net",
        "https://app-field-api-nonprod.azurewebsites.net",
    ],

    # ── Azure region ──────────────────────────────────────────────────────────
    azure_location="northcentralus",
)
