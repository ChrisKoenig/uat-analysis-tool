"""Comprehensive verification of the project refactoring."""
import sys
import os
import json
from pathlib import Path

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'apps'))
os.chdir(PROJECT_ROOT)

failures = 0

print("=== REFACTORING VERIFICATION ===")

# 1. Data files exist in data/
print("\n1. Data files in data/:")
for f in ['retirements.json', 'corrections.json', 'issues_actions.json', 'context_evaluations.json']:
    p = Path('data') / f
    if p.exists():
        d = json.loads(p.read_text(encoding='utf-8'))
        print(f"   OK   {f}")
    else:
        print(f"   FAIL {f} MISSING")
        failures += 1

# 2. search_service loads retirements from data/
print("\n2. search_service data path:")
from shared.search_service import ResourceSearchService
s = ResourceSearchService()
r = s._load_retirements()
count = len(r.get('retirements', []))
if count > 0:
    print(f"   OK   loaded {count} retirements")
else:
    print(f"   FAIL no retirements loaded")
    failures += 1

# 3. Scripts dir exists and has files
print("\n3. Scripts directory:")
scripts = list(Path('scripts').glob('*'))
if len(scripts) >= 15:
    print(f"   OK   {len(scripts)} files in scripts/")
else:
    print(f"   FAIL only {len(scripts)} files in scripts/")
    failures += 1

# 4. Docs dir has the moved files
print("\n4. Docs directory (moved files):")
moved_docs = [
    'SYSTEM_ARCHITECTURE.md', 'KEYVAULT_MIGRATION_COMPLETE.md',
    'TRIAGE_SYSTEM_DESIGN.md', 'AZURE_OPENAI_AUTH_SETUP.md',
    'KEYVAULT_PERMISSIONS_SETUP.md', 'MANAGED_IDENTITY_DEPLOYMENT.md',
    'PROJECT_STATUS.md'
]
for m in moved_docs:
    if (Path('docs') / m).exists():
        print(f"   OK   docs/{m}")
    else:
        print(f"   FAIL docs/{m} MISSING")
        failures += 1

# 5. Tests dir
print("\n5. Tests directory:")
if Path('tests/test_end_to_end.py').exists():
    print("   OK   tests/test_end_to_end.py")
else:
    print("   FAIL tests/test_end_to_end.py MISSING")
    failures += 1

# 6. Gateway requirements moved
print("\n6. Gateway requirements:")
if Path('gateway/requirements.txt').exists():
    print("   OK   gateway/requirements.txt")
else:
    print("   FAIL gateway/requirements.txt MISSING")
    failures += 1

# 7. Old root files should NOT exist
print("\n7. Old locations cleaned up:")
old_files = [
    'SYSTEM_ARCHITECTURE.md', 'TRIAGE_SYSTEM_DESIGN.md',
    'add_ip_to_keyvault.ps1', 'check_kv_config.py',
    'retirements.json', 'corrections.json',
    'test_end_to_end.py', 'requirements-gateway.txt'
]
for f in old_files:
    if Path(f).exists():
        print(f"   FAIL {f} still exists at root!")
        failures += 1
    else:
        print(f"   OK   {f} removed from root")

# 7b. Shared modules should NOT exist at root (moved to shared/)
print("\n7b. Shared modules moved out of root:")
moved_modules = [
    'ai_config.py', 'ado_integration.py', 'blob_storage_helper.py',
    'cache_manager.py', 'embedding_service.py', 'enhanced_matching.py',
    'graph_user_lookup.py', 'hybrid_context_analyzer.py',
    'intelligent_context_analyzer.py', 'keyvault_config.py',
    'llm_classifier.py', 'microservices_client.py', 'search_service.py',
    'servicetree_service.py', 'shared_auth.py', 'vector_search.py',
    'weight_tuner.py',
]
for f in moved_modules:
    if Path(f).exists():
        print(f"   FAIL {f} still exists at root!")
        failures += 1
    else:
        print(f"   OK   {f} removed from root")

# 8. All shared Python modules importable from shared package
print("\n8. Shared module imports (shared.*):")
modules = [
    'shared.ai_config', 'shared.cache_manager', 'shared.search_service',
    'shared.weight_tuner', 'shared.servicetree_service',
    'shared.microservices_client', 'shared.keyvault_config',
    'shared.shared_auth', 'shared.blob_storage_helper',
    'shared.embedding_service', 'shared.llm_classifier',
    'shared.vector_search', 'shared.intelligent_context_analyzer',
    'shared.ado_integration', 'shared.enhanced_matching',
]
for m in modules:
    try:
        __import__(m)
        print(f"   OK   {m}")
    except Exception as e:
        print(f"   FAIL {m}: {e}")
        failures += 1

# 9. Phase 3 directory structure
print("\n9. Phase 3 directory structure:")
phase3_dirs = [
    'apps/field-portal', 'apps/triage', 'apps/triage-ui',
    'services/context-analyzer', 'services/embedding-service',
    'shared', 'shared/config', 'shared/config/environments',
    'infra/bicep', 'infra/deploy', 'infra/docker',
]
for d in phase3_dirs:
    if Path(d).is_dir():
        print(f"   OK   {d}/")
    else:
        print(f"   FAIL {d}/ MISSING")
        failures += 1

# 10. Old Phase 2 locations should NOT exist
print("\n10. Old locations removed (Phase 3):")
old_phase3 = [
    'agents', 'containers', 'config',
    'field-portal', 'triage', 'triage-ui',
]
for d in old_phase3:
    if Path(d).exists():
        print(f"   FAIL {d} still exists at old location!")
        failures += 1
    else:
        print(f"   OK   {d} removed")

print(f"\n{'='*40}")
if failures == 0:
    print("RESULT: ALL CHECKS PASSED")
else:
    print(f"RESULT: {failures} FAILURE(S)")
print(f"{'='*40}")

sys.exit(failures)
