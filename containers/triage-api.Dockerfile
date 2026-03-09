# =============================================================================
# Triage API — FastAPI backend for triage management
# =============================================================================
# Build from project root:
#   az acr build -r acrgcsdevgg4a6y -f containers/triage-api.Dockerfile -t gcs/triage-api:latest .
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY triage/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir openai numpy scikit-learn

# Copy root-level Python modules (shared libraries used by triage routes)
COPY keyvault_config.py ai_config.py shared_auth.py \
  ado_integration.py hybrid_context_analyzer.py \
  intelligent_context_analyzer.py llm_classifier.py \
  embedding_service.py vector_search.py cache_manager.py \
  enhanced_matching.py blob_storage_helper.py ./

# Copy data files used by analyzers
COPY data/corrections.json data/retirements.json data/issues_actions.json data/context_evaluations.json ./

# Copy the triage package
COPY triage/ ./triage/

# Create writable cache directory
RUN mkdir -p /app/cache/ai_cache

EXPOSE 8009

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8009/health')"

CMD ["uvicorn", "triage.triage_service:app", "--host", "0.0.0.0", "--port", "8009"]
