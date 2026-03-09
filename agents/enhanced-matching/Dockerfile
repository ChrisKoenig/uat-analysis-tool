# Enhanced Matching Service
# Phase 6: Microservices Transformation

FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY service.py .

# Copy required source files
COPY ../../enhanced_matching.py ./enhanced_matching.py
COPY ../../hybrid_context_analyzer.py ./hybrid_context_analyzer.py
COPY ../../intelligent_context_analyzer.py ./intelligent_context_analyzer.py
COPY ../../search_service.py ./search_service.py
COPY ../../ai_config.py ./ai_config.py

# Copy data files (if needed locally)
COPY ../../data/retirements.json ./retirements.json
COPY ../../data/corrections.json ./corrections.json
COPY ../../data/issues_actions.json ./issues_actions.json
COPY ../../data/context_evaluations.json ./context_evaluations.json

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8003/health')"

# Run the service
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8003"]
