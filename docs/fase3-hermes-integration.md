# Fase 3 — Integración de Hermes Agent v0.23.4 (`docs/fase3-hermes-integration.md`)

Este documento describe la integración oficial de **NousResearch Hermes Agent (`v0.23.4`)** con el servidor MCP privado de inventario (`services/mcp`) y Telegram para **La Casa del Jean V2** (Issue #11 / F3-02).

---

## 1. Arquitectura y Contenedor Oficial

- **Imagen oficial versionada:** `nousresearch/hermes-agent:v0.23.4` (configurable con `HERMES_IMAGE_TAG=v0.23.4`).
- **Un solo contenedor gateway:** `lcdj_hermes` ejecutando `gateway run` en el perfil `hermes` de `docker-compose.yml`.
- **Persistencia y bootstrap idempotente en `/opt/data`:** Volumen nombrado Linux `hermes_data:/opt/data` (almacena `config.yaml` escribible para migraciones `_config_version`, sesiones, memoria, credenciales OAuth `auth.json` y logs internos).
  - El servicio one-shot `hermes_init` (`alpine:3.20`, `restart: "no"`, perfil `hermes`) ejecuta `services/hermes/scripts/init-hermes-config.sh` **antes** del gateway (`depends_on: hermes_init: condition: service_completed_successfully`).
  - En el primer arranque copia `./services/hermes/config/config.yaml` (`/opt/data/config.template.yaml:ro`) a `/opt/data/config.yaml` con permisos escribibles por el UID efectivo no-root del contenedor. En arranques posteriores **no sobrescribe** `/opt/data/config.yaml`.
  - **Actualizaciones planificadas de configuración:** Para reemplazar `/opt/data/config.yaml` con una nueva plantilla tras un cambio revisado, ejecutar `HERMES_FORCE_CONFIG_RESET=true docker compose --profile hermes run --rm hermes_init` (o fusionar manualmente los cambios en `/opt/data/config.yaml`).
  - `./services/hermes/config/SOUL.md:/opt/data/SOUL.md:ro` y `./services/hermes/plugins/lacasadeljean_mcp_bridge:/opt/data/plugins/lacasadeljean_mcp_bridge:ro` se montan en solo lectura.
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

## 4. Seguridad MCP y Plugin Confiable (`lacasadeljean-mcp-bridge`)

La configuración nativa `mcp_servers` de Hermes únicamente admite cabeceras HTTP estáticas y el hook `pre_tool_call(tool_name, args, task_id, **kwargs)` solo retorna `{"action": "block", "message": "..."}` o `{"action": "modify", "args": {...}}` (no inyecta cabeceras HTTP ni recibe `sender_id`). Por ello:

- **Sin `mcp_servers` estático en `config.yaml`:** Se elimina cualquier definición estática de `mcp_servers` para impedir que el modelo eluda el puente confiable.
- **Plugin oficial v0.23.4 (`services/hermes/plugins/lacasadeljean_mcp_bridge`):**
  1. **`plugin.yaml`:** Declara `provides_tools` (las 9 herramientas de inventario) y `provides_hooks` (`pre_llm_call`, `pre_tool_call`, `on_session_end`).
  2. **`pre_llm_call(session_id, user_message, is_first_turn, model, platform, **kwargs)`:** Extrae `platform == "telegram"` y `sender_id` numérico del contexto confiable del gateway, valida pertenencia a `TELEGRAM_ALLOWED_USERS` y vincula `session_id` / `conversation_id` en `SessionActorRegistry`. Si falta o no está autorizado, bloquea el turno (`{"action": "block", "message": "..."}`). Tras un reinicio o en una sesión sin vinculación previa, `SessionActorRegistry` arranca vacío (**fail-closed**).
  3. **`pre_tool_call(tool_name, args, task_id, **kwargs)`:** Bloquea cualquier herramienta fuera de las 9 autorizadas, cualquier intento de spoofing de argumentos (`telegram_user_id`, `user_id`, `role`, `X-Actor-Assertion`) y cualquier sesión no verificada.
  4. **`ctx.register_tool(...)` + `TrustedMCPBridgeClient`:** Expone las 9 herramientas de inventario directamente al agente; en cada llamada firma un `X-Actor-Assertion` HS256 de corta duración (`30s`, `jti` único) con `MCP_ACTOR_ASSERTION_SECRET` y llama a `http://mcp:8010/mcp` con `Authorization: Bearer <HERMES_MCP_SHARED_SECRET>`.
  5. **Ruta de aprobación para #12 sin exponer secretos al modelo (`TrustedApprovalStore`):** Las escrituras exigen `idempotency_key` y un `approval_proof` firmado y acotado (`telegram_user_id`, `action`, `payload_sha256`). El plugin expone `TrustedApprovalStore.record_human_confirmation(...)` para que el flujo de confirmación de Telegram en #12 registre la aprobación del lado servidor sin exponer jamás `MCP_APPROVAL_SIGNING_SECRET` ni el JWT al LLM.
  6. **Instrucciones (`SOUL.md`):** Exigen propuesta/vista previa estructurada en **PAB (Balboa)** y prohíben publicar o mutar sin confirmación explícita del operador.

---

## 5. Fotos (Visión) y Notas de Voz (STT)

- **Fotos (`vision.enabled: true`):** Hermes analiza imágenes enviadas por Telegram con visión nativa para proponer descripción, color, talla y `alt_text` antes de llamar a `attach_product_photo` (previa confirmación).
- **Notas de voz (`voice_mode.stt`):** Usa el proveedor STT integrado de Hermes **sin levantar un servicio Whisper separado**:
  - **Por defecto (recomendado en 8 GB RAM):** Proveedor hospedado (`HERMES_STT_PROVIDER=openai`, `HERMES_STT_MODEL=whisper-1` usando `VOICE_TOOLS_OPENAI_KEY`, o `groq` con `GROQ_API_KEY`).
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
