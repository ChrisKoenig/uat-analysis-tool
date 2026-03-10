"""
Comprehensive verification of the project refactoring.

Validates that all files, directories, and imports are correctly placed
after each refactoring phase.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is the working directory for relative path checks.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)


# ── 1. Data files ────────────────────────────────────────────────────────────

_DATA_FILES = [
    'retirements.json',
    'corrections.json',
    'issues_actions.json',
    'context_evaluations.json',
]


@pytest.mark.parametrize("filename", _DATA_FILES)
def test_data_files_exist(filename):
    """Each JSON data fixture must exist in data/ and be valid JSON."""
    p = Path('data') / filename
    assert p.exists(), f"data/{filename} missing"
    json.loads(p.read_text(encoding='utf-8'))


# ── 2. search_service loads retirements from data/ ──────────────────────────

def test_search_service_loads_retirements():
    from shared.search_service import ResourceSearchService
    s = ResourceSearchService()
    r = s._load_retirements()
    assert len(r.get('retirements', [])) > 0, "No retirements loaded"


# ── 3. Scripts directory ─────────────────────────────────────────────────────

def test_scripts_directory_has_files():
    scripts = list(Path('scripts').glob('*'))
    assert len(scripts) >= 15, f"Expected ≥15 files in scripts/, found {len(scripts)}"


# ── 4. Docs directory (moved files) ─────────────────────────────────────────

_MOVED_DOCS = [
    'SYSTEM_ARCHITECTURE.md',
    'KEYVAULT_MIGRATION_COMPLETE.md',
    'TRIAGE_SYSTEM_DESIGN.md',
    'AZURE_OPENAI_AUTH_SETUP.md',
    'KEYVAULT_PERMISSIONS_SETUP.md',
    'MANAGED_IDENTITY_DEPLOYMENT.md',
    'PROJECT_STATUS.md',
]


@pytest.mark.parametrize("doc", _MOVED_DOCS)
def test_docs_moved(doc):
    assert (Path('docs') / doc).exists(), f"docs/{doc} missing"


# ── 5. Old root files removed ───────────────────────────────────────────────

_OLD_ROOT_FILES = [
    'SYSTEM_ARCHITECTURE.md',
    'TRIAGE_SYSTEM_DESIGN.md',
    'add_ip_to_keyvault.ps1',
    'check_kv_config.py',
    'retirements.json',
    'corrections.json',
    'test_end_to_end.py',
    'requirements-gateway.txt',
]


@pytest.mark.parametrize("filename", _OLD_ROOT_FILES)
def test_old_root_files_removed(filename):
    assert not Path(filename).exists(), f"{filename} still exists at root"


# ── 6. Shared modules removed from root ─────────────────────────────────────

_MOVED_MODULES = [
    'ai_config.py', 'ado_integration.py', 'blob_storage_helper.py',
    'cache_manager.py', 'embedding_service.py', 'enhanced_matching.py',
    'graph_user_lookup.py', 'hybrid_context_analyzer.py',
    'intelligent_context_analyzer.py', 'keyvault_config.py',
    'llm_classifier.py', 'microservices_client.py', 'search_service.py',
    'servicetree_service.py', 'shared_auth.py', 'vector_search.py',
    'weight_tuner.py',
]


@pytest.mark.parametrize("module", _MOVED_MODULES)
def test_shared_modules_removed_from_root(module):
    assert not Path(module).exists(), f"{module} still exists at root"


# ── 7. Shared module imports ────────────────────────────────────────────────

_SHARED_IMPORTS = [
    'shared.ai_config', 'shared.cache_manager', 'shared.search_service',
    'shared.weight_tuner', 'shared.servicetree_service',
    'shared.microservices_client', 'shared.keyvault_config',
    'shared.shared_auth', 'shared.blob_storage_helper',
    'shared.embedding_service', 'shared.llm_classifier',
    'shared.vector_search', 'shared.intelligent_context_analyzer',
    'shared.ado_integration', 'shared.enhanced_matching',
]


@pytest.mark.parametrize("module_path", _SHARED_IMPORTS)
def test_shared_module_importable(module_path):
    __import__(module_path)


# ── 8. Phase 3+ directory structure ─────────────────────────────────────────

_EXPECTED_DIRS = [
    'apps/field-portal', 'apps/triage', 'apps/triage/ui',
    'services/context-analyzer', 'services/embedding-service',
    'services/gateway',
    'shared', 'shared/config', 'shared/config/environments',
    'infra/bicep', 'infra/deploy', 'infra/docker', 'infra/scripts',
    'logs',
    'tests/unit', 'tests/integration', 'tests/security',
]


@pytest.mark.parametrize("directory", _EXPECTED_DIRS)
def test_expected_directory_exists(directory):
    assert Path(directory).is_dir(), f"{directory}/ missing"


# ── 9. Old locations removed ────────────────────────────────────────────────

_OLD_LOCATIONS = [
    'agents', 'containers', 'config',
    'field-portal', 'triage', 'triage-ui',
    'infrastructure', 'server.js',
]


@pytest.mark.parametrize("name", _OLD_LOCATIONS)
def test_old_location_removed(name):
    assert not Path(name).exists(), f"{name} still exists at old location"
