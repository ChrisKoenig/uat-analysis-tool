# =============================================================================
# Triage API — FastAPI backend for triage management
# =============================================================================
# Build from project root:
#   az acr build -r acrgcsdevgg4a6y -f infra/docker/triage-api.Dockerfile -t gcs/triage-api:latest .
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY apps/triage/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
  && pip install --no-cache-dir openai numpy scikit-learn

# Copy shared services package
COPY shared/ ./shared/

# Copy data files used by analyzers
COPY data/corrections.json data/retirements.json data/issues_actions.json data/context_evaluations.json ./

# Copy the triage package (under apps/ so triage.X imports resolve)
COPY apps/triage/ ./apps/triage/

# Ensure apps/ is on Python path for triage imports
ENV PYTHONPATH="/app:/app/apps"

# Create writable cache directory
RUN mkdir -p /app/cache/ai_cache

EXPOSE 8009

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8009/health')"

CMD ["uvicorn", "triage.triage_service:app", "--host", "0.0.0.0", "--port", "8009"]
