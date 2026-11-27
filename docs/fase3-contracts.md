# Fase 3 — Contratos MCP Privado de Inventario (`docs/fase3-contracts.md`)

Este documento define los contratos técnicos, de seguridad, identidad, confirmación explícita e idempotencia para el servidor MCP privado (`services/mcp`) y su integración con la API FastAPI (`apps/api`) en **La Casa del Jean V2** (Issue #10 / F3-01).

---

## 1. Arquitectura y Límites de Confianza

- **Transporte MCP:** Streamable HTTP (`/mcp`) usando el SDK oficial de Python (`mcp`).
- **Aislamiento de red:** `services/mcp` se ejecuta en la red interna `app_edge` (sin puertos públicos en host y **nunca** conectado a `db_internal`).
- **Sin acceso directo a PostgreSQL:** `services/mcp` **no** contiene dependencias de SQLAlchemy/psycopg ni credenciales de base de datos. Todas las lecturas y escrituras pasan exclusivamente por llamadas HTTP a `apps/api` (`API_INTERNAL_URL`).
- **Preservación de lógica de negocio:** Toda validación Pydantic, RBAC, auditoría inmutable (`audit_events`), manejo de imágenes (Pillow/EXIF) y stock transaccional (`SELECT ... FOR UPDATE`) permanece en `apps/api`.

---

## 2. Identidad del Operador Telegram y Aserción Firmada (`X-Actor-Assertion`)

El modelo de lenguaje (LLM) **nunca** puede declarar su propia identidad. Ninguna herramienta MCP acepta `user_id`, `role` o `telegram_user_id` en sus argumentos.

### 2.1 Autenticación de Transporte
Toda petición HTTP a `services/mcp` debe incluir:
- `Authorization: Bearer <HERMES_MCP_SHARED_SECRET>` (validado en tiempo constante).

### 2.2 Aserción Firmada de Actor (`X-Actor-Assertion`)
Toda invocación de herramienta MCP (`tools/call`) debe incluir el header HTTP `X-Actor-Assertion` con un JWT compacto firmado con `HS256` usando `MCP_ACTOR_ASSERTION_SECRET`:

| Claim | Tipo | Regla |
| --- | --- | --- |
| `iss` | `string` | Debe ser `"hermes-telegram-bridge"` |
| `aud` | `string` | Debe ser `"lacasadeljean-mcp"` |
| `sub` | `string` | `"tg:<telegram_user_id>"` |
| `telegram_user_id` | `integer` | ID numérico positivo verificado por Telegram |
| `jti` | `string` (UUID4) | Nonce único de un solo uso (anti-replay) |
| `iat` | `integer` | Epoch UTC de emisión |
| `exp` | `integer` | Epoch UTC de expiración (`exp - iat <= 60s`) |

**Política fail-closed:**
- Aserción ausente, malformada, con firma inválida, expirada, con TTL > 60s o `jti` repetido → denegada inmediatamente (`401`/`403`).

### 2.3 Mapeo a Usuario Activo y RBAC en FastAPI
- Modelo `users` en PostgreSQL añade columna `telegram_user_id BIGINT UNIQUE NULL` (migración `20261127_0004_add_user_telegram_id.py`).
- Endpoint interno en `apps/api`: `POST /api/v1/internal/mcp/exchange`
  - Protegido por header `X-Internal-MCP-Token: <HERMES_MCP_SHARED_SECRET>` (fail-closed si no está configurado).
  - Request: `{"telegram_user_id": 123456789}`
  - Comportamiento: busca un `User` con `telegram_user_id` coincidente y `is_active = True`. Si no existe o está inactivo, responde `403 Forbidden`.
  - Response `200 OK`: `{ "access_token": "<jwt>", "token_type": "bearer", "expires_at": "...", "user": { "id", "email", "full_name", "role", "is_active" } }` respaldado por una `AuthSession` de corta duración (`5 min`) con `user_agent="mcp-inventory-service"`.
- `services/mcp` usa ese Bearer JWT en todas las llamadas posteriores a `/api/v1/admin/*` y `/api/v1/inventory/*`, preservando RBAC (`admin`, `operator`, `viewer`) y `actor_user_id` en `audit_events`.

---

## 3. Prueba de Confirmación Explícita (`approval_proof`) para Escrituras Sensibles

Las escrituras sensibles requieren una prueba criptográfica firmada, acotada al payload exacto, de corta duración y de un solo uso (`HS256` con `MCP_APPROVAL_SIGNING_SECRET`), emitida por el puente de confirmación en Telegram (o por el firmador de pruebas en `services/mcp/app/security.py` hasta que exista el plugin #12).

### 3.1 Clasificación de Herramientas

| Herramienta | Tipo | RBAC mínimo | Requiere `approval_proof` |
| --- | --- | --- | --- |
| `search_products` | Lectura | `viewer` | No (solo lectura, no muta) |
| `get_product_detail` | Lectura | `viewer` | No (solo lectura, no muta) |
| `get_variant_stock` | Lectura | `viewer` | No (solo lectura, no muta) |
| `create_product_draft` | Escritura borrador | `operator` | No (siempre crea en `draft`) |
| `create_variant` | Escritura borrador | `operator` | No (siempre crea en `draft`) |
| `attach_product_photo` | Escritura media | `operator` | No (validado por Pillow en API) |
| `set_product_price` | **Escritura sensible** | `operator` | **Sí** |
| `record_stock_movement` | **Escritura sensible** | `operator` | **Sí** |
| `set_product_publication_status` | **Escritura sensible** | `operator` | **Sí** |

### 3.2 Claims de `approval_proof`

| Claim | Tipo | Regla |
| --- | --- | --- |
| `iss` | `string` | `"hermes-telegram-approval"` |
| `aud` | `string` | `"lacasadeljean-mcp"` |
| `telegram_user_id` | `integer` | Debe coincidir exactamente con `X-Actor-Assertion.telegram_user_id` |
| `action` | `string` | Nombre exacto de la herramienta sensible |
| `payload_sha256` | `string` | SHA-256 hex del JSON canónico (`sort_keys=True, separators=(",", ":")`) del payload normalizado |
| `jti` | `string` (UUID4) | Nonce de un solo uso; se consume al validar (anti-replay) |
| `iat` | `integer` | Epoch UTC de emisión |
| `exp` | `integer` | Epoch UTC de expiración (`exp - iat <= 120s`) |

---

## 4. Esquemas de Herramientas MCP y Mapeo a Endpoints FastAPI

### 4.1 `search_products` (Solo lectura)
- **Endpoint FastAPI:** `GET /api/v1/admin/products`
- **Parámetros:** `search: str | None`, `category_id: str | None`, `publication_status: "draft" | "published" | "archived" | None`, `page: int = 1`, `page_size: int = 20` (máx 100).
- **Retorno:** `PaginatedResponse[ProductListItem]`.

### 4.2 `get_product_detail` (Solo lectura)
- **Endpoint FastAPI:** `GET /api/v1/admin/products/{product_id}`
- **Parámetros:** `product_id: str` (UUID).
- **Retorno:** `ProductDetail` (incluye variantes, tallas, precios PAB, stock e imágenes).

### 4.3 `get_variant_stock` (Solo lectura)
- **Endpoint FastAPI:** `GET /api/v1/inventory/variants/{variant_id}/balance`
- **Parámetros:** `variant_id: str` (UUID).
- **Retorno:** `StockBalanceOut`.

### 4.4 `create_product_draft`
- **Endpoint FastAPI:** `POST /api/v1/admin/products` (forzando `publication_status="draft"`).
- **Parámetros:** `category_id: str`, `sku: str`, `name: str`, `slug: str`, `description: str | None = None`, `idempotency_key: str | None = None`.
- **Idempotencia / SKU duplicado:** Si `idempotency_key` ya completó con éxito, devuelve el resultado previo con `idempotent_replay: true`. Si el SKU ya existe con otra clave o sin clave, devuelve error estructurado `CONFLICT`.

### 4.5 `create_variant`
- **Endpoint FastAPI:** `POST /api/v1/admin/products/{product_id}/variants` (forzando `publication_status="draft"`).
- **Parámetros:** `product_id: str`, `sku: str`, `size: str`, `color: str`, `color_hex: str | None = None`, `barcode: str | None = None`, `idempotency_key: str | None = None`.
- **Idempotencia / SKU duplicado:** Mismo manejo idempotente que `create_product_draft`.

### 4.6 `set_product_price` (Sensible — requiere `approval_proof`)
- **Endpoint FastAPI:** `POST /api/v1/admin/products/{product_id}/prices`
- **Parámetros:** `product_id: str`, `amount_pab: str` (decimal `>= 0.00`), `compare_at_pab: str | None = None`, `variant_id: str | None = None`, `approval_proof: str`.
- **Moneda:** Siempre `PAB` (validado en MCP y FastAPI).

### 4.7 `record_stock_movement` (Sensible — requiere `approval_proof`)
- **Endpoint FastAPI:** `POST /api/v1/inventory/movements`
- **Parámetros:** `variant_id: str`, `direction: "in" | "out"`, `movement_type: "initial_load" | "restock" | "sale" | "return" | "adjustment" | "damage"`, `quantity: int (> 0)`, `idempotency_key: str` (obligatorio), `reference_type: str | None = None`, `reference_id: str | None = None`, `note: str | None = None`, `approval_proof: str`.
- **Idempotencia:** Delegada a la restricción única `idempotency_key` en PostgreSQL vía FastAPI (`idempotent_replay: true` en reintentos).

### 4.8 `set_product_publication_status` (Sensible — requiere `approval_proof`)
- **Endpoint FastAPI:** `PATCH /api/v1/admin/products/{product_id}`
- **Parámetros:** `product_id: str`, `publication_status: "draft" | "published" | "archived"`, `approval_proof: str`.

### 4.9 `attach_product_photo`
- **Endpoint FastAPI:** `POST /api/v1/admin/products/{product_id}/images/upload` (multipart/form-data)
- **Parámetros:** `product_id: str`, `image_base64: str`, `filename: str`, `content_type: str`, `variant_id: str | None = None`, `alt_text: str | None = None`, `display_order: int = 0`, `is_primary: bool = False`.
- **Seguridad:** FastAPI valida magic bytes, límite de tamaño (`MAX_IMAGE_UPLOAD_BYTES`), re-codifica con Pillow y elimina EXIF.

---

## 5. Variables de Entorno

| Variable | Servicio | Descripción |
| --- | --- | --- |
| `HERMES_MCP_SHARED_SECRET` | `api`, `mcp` | Token Bearer de transporte MCP y autenticación interna `mcp -> api` |
| `MCP_ACTOR_ASSERTION_SECRET` | `mcp` | Secreto HMAC-SHA256 para validar `X-Actor-Assertion` |
| `MCP_APPROVAL_SIGNING_SECRET` | `mcp` | Secreto HMAC-SHA256 para validar `approval_proof` |
| `API_INTERNAL_URL` | `mcp` | URL interna de FastAPI (ej. `http://api:8000`) |
| `MCP_PORT` | `mcp` | Puerto interno de escucha (por defecto `8010`, sin exposición pública) |
