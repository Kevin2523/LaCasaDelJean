# Fase 3 — Integración de Hermes Agent v0.23.4 (`docs/fase3-hermes-integration.md`)

Este documento describe la integración oficial de **NousResearch Hermes Agent (`v0.23.4`)** con el servidor MCP privado de inventario (`services/mcp`) y Telegram para **La Casa del Jean V2** (Issue #11 / F3-02).

---

## 1. Arquitectura y Contenedor Oficial

- **Imagen oficial versionada:** `nousresearch/hermes-agent:v0.23.4` (configurable con `HERMES_IMAGE_TAG=v0.23.4`).
- **Un solo contenedor gateway:** `lcdj_hermes` ejecutando `gateway run` en el perfil `hermes` de `docker-compose.yml`.
- **Persistencia en `/opt/data`:** Volumen nombrado Linux `hermes_data:/opt/data` (almacena sesiones, memoria, credenciales OAuth `auth.json` y logs internos), con archivos de configuración montados en solo lectura:
  - `./services/hermes/config/config.yaml:/opt/data/config.yaml:ro`
  - `./services/hermes/config/SOUL.md:/opt/data/SOUL.md:ro`
  - `./services/hermes/plugins/lacasadeljean_mcp_bridge:/opt/data/plugins/lacasadeljean_mcp_bridge:ro`
- **Sin puertos publicados:** Ni el API server (`8642`) ni el dashboard de Hermes se exponen al host (`gateway.api_server.enabled: false`, `gateway.dashboard.enabled: false` y sin directiva `ports:` en `docker-compose.yml`).
- **Reinicio y rotación de logs:** `restart: unless-stopped` y `logging: json-file` (`max-size: 10m`, `max-file: 3`).
- **Aislamiento de red:** Conectado únicamente a `app_edge` (habla con `http://mcp:8010/mcp`). **Nunca** conectado a `db_internal` ni con acceso directo a PostgreSQL.

---

## 2. Presupuesto de Recursos (Servidor 8 GB RAM / Ryzen 3)

| Servicio | Límite CPU | Límite RAM | Notas |
| --- | --- | --- | --- |
| `postgres` | `0.75` | `512M` | Red `db_internal` |
| `api` | `1.00` | `768M` | FastAPI + Pillow |
| `web` | `0.75` | `384M` | Angular + Nginx |
| `mcp` | `0.50` | `256M` | MCP Streamable HTTP stateless |
| `hermes` | `1.50` | `1536M` (1.5 GB) | Gateway Hermes v0.23.4 (rango recomendado 1.5–2 GB, mínimo 1 GB) |
| `cloudflared` | `0.25` | `128M` | Opcional (Fase 4) |

- **Sin navegador embebido (`browser` deshabilitado), sin LLM local y sin contenedor Whisper separado** por defecto para proteger la RAM del servidor de 8 GB.

---

## 3. Telegram (Long Polling, Lista Blanca Numérica y Sesiones por Usuario)

- **Modo:** Long polling saliente (`gateway.telegram.mode: "polling"`), un solo bot (`TELEGRAM_BOT_TOKEN`). No requiere webhook público ni puerto entrante.
- **Control de acceso:** `TELEGRAM_ALLOWED_USERS` con IDs numéricos de Telegram separados por coma (obtenidos vía `@userinfobot`), nunca usernames `@handle`.
- **Aislamiento de sesiones:** `session_scope: "per_user"`, `allow_groups: false`.

---

## 4. Seguridad MCP y Plugin Confiable (`lacasadeljean_mcp_bridge`)

La configuración nativa de `mcp_servers` en Hermes solo soporta cabeceras estáticas (`Authorization: Bearer ${HERMES_MCP_SHARED_SECRET}`). Por ello, el plugin confiable `services/hermes/plugins/lacasadeljean_mcp_bridge` intercepta `pre_tool_call` en modo **fail-closed**:

1. **Lista blanca estricta de herramientas:** Solo permite las 9 herramientas del MCP de inventario (`search_products`, `get_product_detail`, `get_variant_stock`, `create_product_draft`, `create_variant`, `attach_product_photo`, `set_product_price`, `record_stock_movement`, `set_product_publication_status`). Bloquea terminal, SQL directo, archivos y navegador.
2. **Anti-spoofing de identidad:** Rechaza inmediatamente cualquier llamada en la que el modelo intente pasar `telegram_user_id`, `user_id`, `actor_id`, `role` o `X-Actor-Assertion` como argumento.
3. **Aserción firmada por llamada (`X-Actor-Assertion`):** Extrae el `telegram_user_id` numérico exclusivamente del contexto verificado de la sesión Telegram, valida pertenencia a `TELEGRAM_ALLOWED_USERS` y firma un JWT HS256 de corta duración (`30s`, `jti` único) con `MCP_ACTOR_ASSERTION_SECRET`.
4. **Confirmación explícita (`approval_proof`) en toda escritura:** Valida localmente (y `services/mcp` vuelve a validar y consumir de forma duradera en PostgreSQL) que exista un `approval_proof` firmado con `MCP_APPROVAL_SIGNING_SECRET`, acotado al `telegram_user_id`, `action` y `payload_sha256` exactos, junto con `idempotency_key` obligatorio.
5. **Instrucciones (`SOUL.md`):** Exigen propuesta/vista previa estructurada en **PAB (Balboa)** y prohíben publicar o mutar sin confirmación explícita del operador.

---

## 5. Fotos (Visión) y Notas de Voz (STT)

- **Fotos (`vision.enabled: true`):** Hermes analiza imágenes enviadas por Telegram con visión nativa para proponer descripción, color, talla y `alt_text` antes de llamar a `attach_product_photo` (previa confirmación).
- **Notas de voz (`voice_mode.stt`):** Usa el proveedor STT integrado de Hermes **sin levantar un servicio Whisper separado**:
  - **Por defecto (recomendado en 8 GB RAM):** Proveedor hospedado (`HERMES_STT_PROVIDER=openai`, `HERMES_STT_MODEL=whisper-1`, o `groq` con `GROQ_API_KEY`).
  - **Opcional local:** `faster-whisper` (`tiny` o `base` en CPU) **solo** si el operador lo elige explícitamente y el monitoreo de RAM/CPU del Ryzen 3 lo permite.

---

## 6. Proveedores LLM y Facturación (Codex OAuth vs OpenAI API vs Nous Portal)

> **Importante sobre facturación:** Tener una suscripción **ChatGPT Plus / Pro** **NO** cubre el uso de la API de OpenAI (`OPENAI_API_KEY`) ni el STT hospedado de OpenAI (`whisper-1`). Son facturaciones separadas.

| Ruta | Configuración en Hermes v0.23.4 | Facturación / Notas |
| --- | --- | --- |
| **Codex OAuth / Plan ChatGPT** | Ejecutar una vez: `docker compose --profile hermes run --rm hermes auth add openai-codex` (guarda tokens en `/opt/data/auth.json`) y configurar `HERMES_LLM_PROVIDER=openai-codex` | Usa el plan ChatGPT vinculado por OAuth para el LLM. **No** cubre llamadas a la OpenAI API ni STT hospedado (`whisper-1`); para voz usa Groq API o `faster-whisper` local si hay recursos. |
| **OpenAI API (facturación separada)** | `HERMES_LLM_PROVIDER=openai`, `OPENAI_API_KEY=...` en `.env` | Facturación por uso en platform.openai.com. Cubre tanto LLM como STT hospedado (`whisper-1`). |
| **Nous Portal** | `HERMES_LLM_PROVIDER=nous`, `NOUS_API_KEY=...` en `.env` | Facturación/cuota en Nous Research Portal. Para STT hospedado configurar aparte `OPENAI_API_KEY` o `GROQ_API_KEY`. |

---

## 7. Operación con Docker Compose

```bash
# 1. Validar configuración de Compose (con perfiles mcp y hermes)
docker compose --profile mcp --profile hermes config

# 2. (Opcional) Configurar OAuth de Codex de forma interactiva en /opt/data
docker compose --profile hermes run --rm hermes auth add openai-codex

# 3. Levantar stack completo con MCP + Hermes
docker compose --profile mcp --profile hermes up -d
```

---

## 8. Fuentes Oficiales Verificadas

- NousResearch Hermes Agent `v0.23.4` (Docker image `nousresearch/hermes-agent:v0.23.4`, `gateway run`, persistencia `/opt/data`): Documentación oficial de Nous Research (`https://hermes-agent.nousresearch.com/`).
- Configuración de Telegram (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`), `mcp_servers`, `plugins` (`pre_tool_call`), `voice_mode` (`faster-whisper` / proveedores hospedados) y `hermes auth add openai-codex`: Documentación oficial de NousResearch Hermes Agent.
- Contratos privados MCP de inventario: [docs/fase3-contracts.md](./fase3-contracts.md) (Issue #10).
