FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies for data processing pipelines
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser \
    && mkdir -p /app /home/appuser \
    && chown -R appuser:appuser /app /home/appuser

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')" || exit 1

# Default: run migrations then start Gunicorn with Uvicorn workers.
# Override in compose for Celery workers/beat.
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --access-logfile - --error-logfile - --timeout 60 --keep-alive 5 --max-requests 10000"]
