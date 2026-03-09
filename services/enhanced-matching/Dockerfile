# Enhanced Matching Service
# Phase 6: Microservices Transformation

FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY service.py .

# Copy shared services package
COPY ../../shared/ ./shared/

# Copy data files (if needed locally)
COPY ../../data/ ./data/

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8003/health')"

# Run the service
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8003"]
