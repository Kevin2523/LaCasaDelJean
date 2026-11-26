# ==============================================================================
# Fase 0 Placeholder Dockerfile - Hermes / MCP / Telegram Worker
# La integración de Hermes, MCP y Telegram se implementará en Fase 3.
# ==============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system hermesgroup && adduser --system --ingroup hermesgroup hermesuser \
    && chown -R hermesuser:hermesgroup /app

USER hermesuser

# Placeholder de Fase 0: en Fase 3 se reemplazará por el runner de Hermes/MCP/Telegram
CMD ["python", "-c", "import time; print('Hermes Fase 0 placeholder'); time.sleep(3600)"]
