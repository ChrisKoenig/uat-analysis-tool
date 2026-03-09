FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY service.py .

# Copy shared services package
COPY ../../shared/ ./shared/

# Expose port
EXPOSE 8006

# Run service
CMD ["python", "service.py"]
