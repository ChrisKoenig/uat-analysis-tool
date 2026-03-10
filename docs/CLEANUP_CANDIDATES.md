# Cleanup Candidates

Files identified during Phase 4 refactoring that are candidates for deletion
or archival. Grouped by category with rationale.

---

## Delete — Superseded

| File | Reason |
|------|--------|
| `launcher.py` | Desktop GUI launcher; superseded by `start_dev.ps1` (last real work: Feb 11) |
| `api/ado_api.py` | Flask blueprint; superseded by `services/gateway/routes/ado.py` (FastAPI) |
| `api/context_api.py` | Flask blueprint; superseded by `services/gateway/routes/analyze.py` (FastAPI) |
| `api/quality_api.py` | Flask blueprint; superseded by `services/gateway/routes/quality.py` (FastAPI) |
| `api/search_api.py` | Flask blueprint; superseded by `services/gateway/routes/search.py` (FastAPI) |
| `api/uat_api.py` | Flask blueprint; superseded by `services/gateway/routes/uat.py` (FastAPI) |
| `api/__init__.py` | Package init for deleted Flask blueprints |
| `scripts/update_openai_deployment_name.py` | Deployment names moved to AppConfig, no longer stored in Key Vault |
| `scripts/disable_unused_extensions.ps1` | VM-related; no VMs in current architecture |

## Archive — One-time migrations (completed)

These scripts did their job and are documented as complete. Move to `scripts/archive/`.

| File | Completed |
|------|-----------|
| `scripts/migrate_secrets_to_keyvault.py` | Jan 2026 — documented in KEYVAULT_MIGRATION_COMPLETE.md |
| `scripts/migrate_to_azure_storage.py` | Phase 2 — JSON → Azure Blob migration |
| `scripts/authenticate_interactive.py` | Superseded by `DefaultAzureCredential` in `shared/shared_auth.py` |
| `scripts/find_subscription_tenant.py` | Resolved; documented in AZURE_OPENAI_AUTH_SETUP.md |
| `scripts/resolve_tenant_id.py` | Resolved; documented in AZURE_OPENAI_AUTH_SETUP.md |
| `scripts/check_token_tenant.py` | Setup verification complete |
| `scripts/get_resource_tenant.py` | Setup verification complete |
| `scripts/assign_user_openai_role.py` | RBAC now managed via Azure Portal |
| `scripts/add_openai_secrets_python.py` | One-time Key Vault seeding complete |
| `scripts/add_openai_to_keyvault.ps1` | One-time Key Vault seeding complete |
| `scripts/add_ip_to_keyvault.ps1` | Firewall IP whitelist setup complete |
| `scripts/configure_managed_identity.ps1` | MI deployed; documented in MANAGED_IDENTITY_DEPLOYMENT.md |
| `scripts/configure_managed_identity_manual.ps1` | Backup to above |
| `scripts/configure_keyvault_security.ps1` | RBAC + firewall setup complete |
| `scripts/ensure_cosmos_firewall_ip.ps1` | Cosmos firewall configured |

## Keep — Still active

| File | Reason |
|------|--------|
| `api_gateway.py` | Core FastAPI gateway; used by field-portal and microservices client |
| `admin_service.py` | Flask admin dashboard; started by launcher/start_dev.ps1 |
| `start_dev.ps1` | Primary local dev startup script |
| `scripts/check_kv_config.py` | Useful for troubleshooting Key Vault config |
| `scripts/test_keyvault_integration.ps1` | Health check utility |
| `scripts/seed_classification_config.py` | Current build requirement (ENG-010) |
