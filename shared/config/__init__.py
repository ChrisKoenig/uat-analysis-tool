"""
Environment-Aware Application Configuration
============================================

Selects the active environment via the APP_ENV environment variable:

  APP_ENV=dev       — local developer workstation (default)
  APP_ENV=preprod   — non-production Azure deployment
  APP_ENV=prod      — production Azure deployment

Usage:
    from shared.config import get_app_config
    cfg = get_app_config()
    print(cfg.tenant_id)
    print(cfg.key_vault_url)       # computed property
    print(cfg.cosmos_endpoint)     # computed property

Individual values can always be overridden by the environment variables listed
in each field's comment below. This is useful in containers / App Service where
you set `APP_ENV=preprod` and override just a few values as app settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

# Which environment are we running in?  Default to "dev" so nothing breaks
# if the variable is absent on a local workstation.
APP_ENV: str = os.environ.get("APP_ENV", "dev").lower()


@dataclass
class AppConfig:
    """
    Full application configuration for one deployment environment.
    All compute properties (URLs built from account names) are @property.

    Fields WITHOUT defaults must be declared first (Python dataclass rule).
    """

    # ── Required fields (no defaults) ────────────────────────────────────────
    app_env: str                           # "dev" | "preprod" | "prod"
    tenant_id: str                         # AAD tenant for this workload
    subscription_id: str                   # Azure subscription
    resource_group: str                    # Azure resource group
    key_vault_name: str                    # Env-var override: KEY_VAULT_NAME
    cosmos_account: str                    # Env-var override: COSMOS_ACCOUNT
    openai_account: str                    # Env-var override: OPENAI_ACCOUNT

    # ── Cosmos DB (optional) ──────────────────────────────────────────────────
    cosmos_database: str = "triage-management"

    @property
    def cosmos_endpoint(self) -> str:
        return f"https://{self.cosmos_account}.documents.azure.com:443/"

    # ── Key Vault (computed) ──────────────────────────────────────────────────
    @property
    def key_vault_url(self) -> str:
        return f"https://{self.key_vault_name}.vault.azure.net/"

    # ── Azure OpenAI (optional) ───────────────────────────────────────────────
    openai_api_version: str = "2024-08-01-preview"
    embedding_model: str = "text-embedding-3-large"
    classification_model: str = "gpt-4o"
    embedding_deployment: str = "text-embedding-3-large"
    classification_deployment: str = "gpt-4o-standard"

    @property
    def openai_endpoint(self) -> str:
        return f"https://{self.openai_account}.openai.azure.com/"

    # ── Azure Storage ─────────────────────────────────────────────────────────
    storage_account: str = ""
    storage_container: str = "gcs-data"

    # ── Azure DevOps ──────────────────────────────────────────────────────────
    # Env-var overrides: ADO_ORGANIZATION, ADO_PROJECT, ADO_TFT_ORGANIZATION
    ado_organization: str = ""          # Primary org (UAT write target)
    ado_project: str = ""               # Primary project
    ado_tft_organization: str = ""      # TFT feature-search org (read-only)
    ado_tft_project: str = "Technical Feedback"
    # The stable Microsoft corporate tenant used for TFT/ADO auth
    microsoft_tenant_id: str = "72f988bf-86f1-41af-91ab-2d7cd011db47"

    # ── Managed Identity ──────────────────────────────────────────────────────
    managed_identity_name: str = ""
    managed_identity_client_id: str = ""
    managed_identity_object_id: str = ""

    # ── Container / ACR ──────────────────────────────────────────────────────
    acr_name: str = ""
    container_env_name: str = ""

    # ── Microservice ports ────────────────────────────────────────────────────
    api_gateway_port: int = 8000
    context_analyzer_port: int = 8001
    search_service_port: int = 8002
    enhanced_matching_port: int = 8003
    uat_management_port: int = 8004
    llm_classifier_port: int = 8005
    embedding_service_port: int = 8006
    vector_search_port: int = 8007
    admin_service_port: int = 8008
    triage_api_port: int = 8009
    triage_ui_port: int = 3000
    field_api_port: int = 8010
    field_ui_port: int = 3001
    main_app_port: int = 5003

    # ── App behaviour ────────────────────────────────────────────────────────
    # Env-var override: APP_DEBUG=true|false
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: List[str] = field(default_factory=list)

    # ── Azure region ─────────────────────────────────────────────────────────
    azure_location: str = "northcentralus"

    # ── Helpers ══════════════════════════════════════════════════════════════

    def service_url(self, port: int, host: str = "localhost") -> str:
        """Build a local service URL from a port number."""
        return f"http://{host}:{port}"

    @property
    def service_port_map(self) -> dict:
        """Mapping of service name → port, used by admin_service and launcher."""
        return {
            "main-app":           self.main_app_port,
            "api-gateway":        self.api_gateway_port,
            "context-analyzer":   self.context_analyzer_port,
            "search-service":     self.search_service_port,
            "enhanced-matching":  self.enhanced_matching_port,
            "uat-management":     self.uat_management_port,
            "llm-classifier":     self.llm_classifier_port,
            "embedding-service":  self.embedding_service_port,
            "vector-search":      self.vector_search_port,
        }


def get_app_config() -> AppConfig:
    """
    Return the AppConfig for the current environment.

    Environment is determined by APP_ENV (default: 'dev').
    Any field can be overridden by its corresponding environment variable
    (see _apply_env_overrides below).
    """
    env = APP_ENV

    if env == "dev":
        from shared.config.dev import DEV_CONFIG as cfg
    elif env in ("preprod", "pre-prod", "staging"):
        from shared.config.preprod import PREPROD_CONFIG as cfg
    elif env == "prod":
        from shared.config.prod import PROD_CONFIG as cfg
    elif env == "chkoenig":
        from shared.config.chkoenig import CHKOENIG_CONFIG as cfg
    else:
        raise ValueError(
            f"Unknown APP_ENV '{env}'. Valid values: dev, preprod, prod, chkoenig"
        )

    _apply_env_overrides(cfg)
    return cfg


def _apply_env_overrides(cfg: AppConfig) -> None:
    """
    Apply individual environment variable overrides on top of the base config.
    Allows containers / App Service to pin APP_ENV=preprod and still adjust
    a single value (e.g. KEY_VAULT_NAME) without touching source files.
    """
    _str_override(cfg, "tenant_id",                  "AZURE_TENANT_ID")
    _str_override(cfg, "subscription_id",            "AZURE_SUBSCRIPTION_ID")
    _str_override(cfg, "key_vault_name",             "KEY_VAULT_NAME", "AZURE_KEY_VAULT_NAME")
    _str_override(cfg, "cosmos_account",             "COSMOS_ACCOUNT")
    _str_override(cfg, "openai_account",             "OPENAI_ACCOUNT")
    _str_override(cfg, "storage_account",            "STORAGE_ACCOUNT")
    _str_override(cfg, "ado_organization",           "ADO_ORGANIZATION")
    _str_override(cfg, "ado_project",                "ADO_PROJECT")
    _str_override(cfg, "classification_deployment",  "AZURE_OPENAI_CLASSIFICATION_DEPLOYMENT")
    _str_override(cfg, "embedding_deployment",       "AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    _bool_override(cfg, "debug",                     "APP_DEBUG")
    _str_override(cfg, "log_level",                  "LOG_LEVEL")


def _str_override(cfg: AppConfig, attr: str, *env_vars: str) -> None:
    for var in env_vars:
        val = os.environ.get(var)
        if val:
            setattr(cfg, attr, val)
            return


def _bool_override(cfg: AppConfig, attr: str, *env_vars: str) -> None:
    for var in env_vars:
        val = os.environ.get(var)
        if val is not None:
            setattr(cfg, attr, val.lower() in ("true", "1", "yes"))
            return


# ── JSON-based config loading ────────────────────────────────────────────────

import dataclasses as _dc
import json as _json
from pathlib import Path as _Path

_APP_CONFIG_FIELDS = {f.name for f in _dc.fields(AppConfig)}


def _load_from_json(json_filename: str) -> AppConfig:
    """
    Load an AppConfig from a JSON file in config/environments/.

    Keys in the JSON that do not correspond to AppConfig fields (e.g.
    PS1-only values like ``app_services``) are silently ignored.
    """
    json_path = _Path(__file__).parent / "environments" / json_filename
    with open(json_path, encoding="utf-8") as fh:
        data = _json.load(fh)

    kwargs = {k: v for k, v in data.items() if k in _APP_CONFIG_FIELDS}
    return AppConfig(**kwargs)
