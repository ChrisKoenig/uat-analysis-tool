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

# Copy shared services package
COPY services/ ./services/

# Copy data files used by analyzers
COPY data/corrections.json data/retirements.json data/issues_actions.json data/context_evaluations.json ./

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
