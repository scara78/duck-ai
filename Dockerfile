FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY duck_ai/ ./duck_ai/
COPY .env.example .env

# Create non-root user
RUN useradd -m -u 1000 duckuser && chown -R duckuser:duckuser /app
USER duckuser

# Expose port
EXPOSE 8788

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8788/health', timeout=5)" || exit 1

# Run server
CMD ["uvicorn", "duck_ai.server:app", "--host", "0.0.0.0", "--port", "8788"]