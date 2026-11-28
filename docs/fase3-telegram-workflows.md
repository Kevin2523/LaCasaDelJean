# Fase 3 — Flujos de Telegram y Confirmación Explícita (`docs/fase3-telegram-workflows.md`)

Documentación técnica del Issue #12 (**F3-03**) para operar el catálogo e inventario de **La Casa del Jean V2** desde Telegram a través de **Hermes Agent v0.23.4** (`lacasadeljean-mcp-bridge`) y el servidor MCP privado (`services/mcp`).

---

## 1. Integración Oficial Hermes v0.23.4 (Hooks + Herramientas)

- **Herramientas expuestas al LLM (`provides_tools`):** Únicamente las 3 herramientas de **solo lectura** (`search_products`, `get_product_detail`, `get_variant_stock`) y la herramienta **no mutante** `propose_inventory_write`.
- **Las 6 herramientas de escritura NO están expuestas al modelo:** `pre_tool_call` bloquea cualquier intento del modelo de invocar directamente `create_product_draft`, `create_variant`, `attach_product_photo`, `set_product_price`, `record_stock_movement` o `set_product_publication_status`.
- **Hook oficial `post_gateway_admission`:** Intercepta respuestas humanas `CONFIRMAR <proposal_id>` / `CANCELAR <proposal_id>` tras la autenticación del gateway, valida `platform == "telegram"`, `source.user_id` en `TELEGRAM_ALLOWED_USERS`, coherencia de DM privado (`chat_type == "dm"`, `chat_id == user_id`) y vinculación estable `telegram:dm:<uid>` (independiente de la diferencia entre el UUID de sesión Hermes y el `session_key` de enrutamiento `agent:main:telegram:dm:<chat_id>`). Todo el flujo está protegido para devolver siempre `{"action": "handled", ...}` ante cualquier error inesperado (evitando comportamiento fail-open hacia el LLM).
- **Roles reales de backend:** `admin` y `operator` (mapeados por `telegram_user_id` en FastAPI; RBAC aplicado en FastAPI/MCP).

---

## 2. Flujo Propuesta → Vista Previa → Confirmación / Cancelación

1. El operador envía texto, foto o nota de voz (STT nativo de Hermes) en su chat privado con el bot único.
2. `pre_llm_call` valida `TELEGRAM_ALLOWED_USERS` y vincula `session_id` / `session_key` al `telegram_user_id` (fail-closed tras reinicio).
3. El modelo consulta catálogo y llama a `propose_inventory_write` (no muta inventario), devolviendo una vista previa estructurada en **PAB** con `proposal_id`, `idempotency_key` y caducidad (`HERMES_PROPOSAL_TTL_SECONDS`, default `120s`).
4. El operador responde explícitamente `CONFIRMAR <proposal_id>` o `CANCELAR <proposal_id>`.
5. `post_gateway_admission` intercepta el comando fuera del LLM, emite `approval_proof` de un solo uso en `TrustedApprovalStore` y ejecuta la mutación vía MCP → FastAPI con auditoría e idempotencia durable.
6. Cualquier intento de otro usuario, otra sesión, propuesta expirada, cancelada o repetida falla cerrado (`UNAUTHORIZED_APPROVER`, `SESSION_MISMATCH`, `PROPOSAL_EXPIRED`, `PROPOSAL_CANCELLED`, `APPROVAL_REPLAYED`).

---

## 3. Fotos (3 Opciones del Operador) y Límite de Búsqueda Externa

`propose_inventory_write` integra `media.py` para `attach_product_photo`:

- **`original`:** Valida con Pillow y elimina metadatos EXIF manteniendo dimensiones originales.
- **`pillow_optimize`:** Auto-orienta, redimensiona, aplica mejora suave de contraste/nitidez, convierte a WebP y elimina EXIF.
- **`exact_model_web_search`:** Solo para tenis o productos comerciales verificables. Exige coincidencia exacta de marca, modelo y código (`MODEL_IDENTITY_MISMATCH` / `MODEL_CODE_MISMATCH`) **y** licencia permitida (`brand_press_kit`, `authorized_distributor`, `merchant_owned`, `cc0`, `cc_by`, `cc_by_sa`, `public_domain`). Rechaza copyright arbitrario o licencia desconocida (`COPYRIGHT_LICENSE_REJECTED`).
  - **Límite documentado (búsqueda externa):** El plugin no hace scraping web arbitrario. Si no hay un proveedor autorizado de búsqueda de imágenes configurado que entregue un candidato con licencia verificada (`external_image_candidate`), falla cerrado con `EXTERNAL_SEARCH_PROVIDER_REQUIRED` y solicita al operador elegir `original` o `pillow_optimize`.
  - **Límite documentado (staging de adjuntos Telegram — pendiente):** `propose_inventory_write` recibe `image_base64` ya preparado; los hooks actuales de plugins Hermes v0.23.4 (`pre_tool_call` / `post_gateway_admission`) no exponen bytes crudos de adjuntos binarios de Telegram directamente al plugin. Por ello, el camino de foto desde adjunto nativo de Telegram queda explícitamente **pendiente** de staging confiable en una iteración posterior (sin crear un segundo bot), mientras que el procesamiento (`original`, `pillow_optimize`, `exact_model_web_search` con verificación de licencia) está implementado y probado sobre payloads `image_base64` ya preparados.
- **Notas de voz (STT nativo):** Usan el STT integrado de Hermes (`config.yaml` → `stt`), sin segundo bot ni servicio Whisper separado. Con `HERMES_STT_PROVIDER=openai`, Hermes requiere la variable `VOICE_TOOLS_OPENAI_KEY` (no `OPENAI_API_KEY`); con `groq`, requiere `GROQ_API_KEY`.

---

## 4. Demo Local End-to-End (Flujo Gateway Oficial, sin token real)

```bash
PYTHONPATH=. uv run --with httpx --with pyjwt --with pillow --with "mcp<2" --with starlette --with pydantic-settings \
  python services/hermes/scripts/demo_telegram_e2e.py
```
