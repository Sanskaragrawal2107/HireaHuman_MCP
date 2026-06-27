FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .
COPY .env .

# Health check via HTTP transport
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Run via HTTP transport in container environments
CMD ["python", "server.py", "--transport", "http", "--port", "8000", "--host", "0.0.0.0"]
