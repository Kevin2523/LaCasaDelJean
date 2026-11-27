# ==============================================================================
# Fase 0 Placeholder Dockerfile - Backend API (FastAPI + Pillow)
# El código de la API se implementará en Fase 1+.
# ==============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser \
    && mkdir -p /app/storage/media \
    && chown -R appuser:appgroup /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appgroup pyproject.toml alembic.ini ./
COPY --chown=appuser:appgroup alembic ./alembic
COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup tests ./tests

USER appuser

EXPOSE 8000

# Placeholder de Fase 0: en Fase 1 se reemplazará por `uvicorn app.main:app`
CMD ["python", "-m", "http.server", "8000"]
