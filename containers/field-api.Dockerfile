# =============================================================================
# Field Portal API — FastAPI backend for 9-step field submission flow
# =============================================================================
# Build from project root:
#   az acr build -r acrgcsdevgg4a6y -f containers/field-api.Dockerfile -t gcs/field-api:latest .
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
# (field-portal has no own requirements.txt — reuse triage base + extras)
COPY triage/requirements.txt ./base-requirements.txt
RUN pip install --no-cache-dir -r base-requirements.txt \
    && pip install --no-cache-dir openai numpy scikit-learn

# Copy root-level Python modules (shared libraries)
COPY keyvault_config.py ai_config.py shared_auth.py \
     ado_integration.py hybrid_context_analyzer.py \
     intelligent_context_analyzer.py llm_classifier.py \
     embedding_service.py vector_search.py cache_manager.py \
     enhanced_matching.py blob_storage_helper.py ./

# Copy data files used by analyzers
COPY corrections.json retirements.json issues_actions.json context_evaluations.json ./

# Copy triage package (field-portal imports triage.config.cosmos_config)
COPY triage/ ./triage/

# Copy field-portal API as field_portal (underscore for valid Python package name)
# Preserves the 2-level nesting so main.py's sys.path resolution still works:
#   dirname(__file__) = /app/field_portal/api  →  ../.. = /app
COPY field-portal/api/ ./field_portal/api/
RUN touch ./field_portal/__init__.py

# Create writable cache directory
RUN mkdir -p /app/cache/ai_cache /app/field_portal/cache

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8010/api/field/health')"

CMD ["uvicorn", "field_portal.api.main:app", "--host", "0.0.0.0", "--port", "8010"]
