# Fase 3 — Flujos de Telegram y Confirmación Explícita (`docs/fase3-telegram-workflows.md`)

Documentación técnica del Issue #12 (**F3-03**) para operar el catálogo e inventario de **La Casa del Jean V2** desde Telegram a través de **Hermes Agent v0.23.4** y el servidor MCP privado (`services/mcp`).

---

## 1. Arquitectura de Bot Único y Multi-Operador

- **Un solo bot de Telegram:** Gestionado por Hermes (`gateway run`) con `TELEGRAM_BOT_TOKEN` y `TELEGRAM_ALLOWED_USERS` (IDs numéricos).
- **Mapeo a roles de backend:** Cada llamada a herramienta MCP firma un `X-Actor-Assertion` por operador; `services/mcp` lo intercambia en FastAPI por un JWT con el rol real del operador (`admin` / `vendedor`).
- **Aislamiento por usuario/sesión:** Cada operador mantiene su propia conversación y sus propias propuestas pendientes (`ProposalWorkflowManager`), compartiendo el mismo catálogo en FastAPI/PostgreSQL.
- **Fail-closed:** Usuarios no listados en `TELEGRAM_ALLOWED_USERS` o sin mapeo activo en backend son rechazados antes de ejecutar cualquier herramienta.

---

## 2. Flujo Propuesta → Vista Previa → Confirmación / Cancelación

Implementado en `services/hermes/plugins/lacasadeljean_mcp_bridge/workflows.py`:

1. **Propuesta (`create_proposal`):** Valida allowlist, acción en `WRITE_TOOLS`, ausencia de argumentos falsificados, genera/vincula `idempotency_key` y calcula `scoped_payload_sha256`. **No muta inventario.**
2. **Vista previa (`format_proposal_preview`):** Presenta los datos exactos (operación, origen `text`/`photo`/`voice`, precios en **PAB**, clave de idempotencia y tiempo de expiración `HERMES_PROPOSAL_TTL_SECONDS`, por defecto `120s`).
3. **Confirmación explícita (`confirm_proposal`):**
   - Verifica dueño (`telegram_user_id`), misma sesión (`session_id`), estado `pending` y no expiración.
   - Emite un `approval_proof` firmado de **un solo uso** en `TrustedApprovalStore` (nunca expuesto al LLM) vinculado a `(telegram_user_id, action, exact args, idempotency_key)`.
   - Ejecuta la escritura exclusivamente vía `TrustedMCPBridgeClient` → `services/mcp` → FastAPI (con auditoría e idempotencia durable en PostgreSQL).
4. **Cancelación (`cancel_proposal`):** Marca la propuesta como `cancelled`; cualquier confirmación posterior falla cerrado (`PROPOSAL_CANCELLED`).
5. **Anti-replay e idempotencia:** Re-confirmar una propuesta ejecutada falla con `APPROVAL_REPLAYED`; reintentar con la misma `idempotency_key` no duplica la mutación.

---

## 3. Fotos (3 Opciones del Operador) y Notas de Voz

Implementado en `services/hermes/plugins/lacasadeljean_mcp_bridge/media.py` y `services/hermes/config/SOUL.md`:

- **Opción 1 — Foto original (`original`):** Valida con Pillow y elimina metadatos EXIF manteniendo dimensiones originales.
- **Opción 2 — Optimización con Pillow (`pillow_optimize`):** Auto-orienta, redimensiona, aplica mejora suave de contraste/nitidez, convierte a WebP y elimina EXIF.
- **Opción 3 — Búsqueda web de modelo exacto (`exact_model_web_search`):** Solo para tenis o productos comerciales verificables. Exige coincidencia exacta de marca, modelo y código (`MODEL_IDENTITY_MISMATCH` / `MODEL_CODE_MISMATCH`) **y** licencia permitida (`brand_press_kit`, `authorized_distributor`, `merchant_owned`, `cc0`, `cc_by`, `cc_by_sa`, `public_domain`). Rechaza cualquier imagen con copyright arbitrario o licencia desconocida (`COPYRIGHT_LICENSE_REJECTED`).
- **Notas de voz:** Usan el STT nativo configurado en Hermes (`config.yaml` → `stt`), sin segundo bot ni servicio Whisper separado.

---

## 4. Demo Local End-to-End (sin token real)

```bash
PYTHONPATH=. uv run --with httpx --with pyjwt --with pillow --with "mcp<2" --with starlette --with pydantic-settings \
  python services/hermes/scripts/demo_telegram_e2e.py
```
