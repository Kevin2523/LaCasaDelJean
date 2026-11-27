# Contratos de Datos Compartidos — Fase 1 (La Casa del Jean V2)

> **Estado:** Aprobado para implementación de Fase 1 (Issue #4 — F1-01).
> **Ámbito:** Contratos compartidos entre Base de Datos (`apps/api/app/models`), Servicios de Dominio, API REST (Fase 1B+) y Frontend (`apps/web`).

---

## 1. Convenciones Globales

| Regla | Estándar | Notas |
| --- | --- | --- |
| **Identificadores** | `UUID` (v4, `uuid.UUID`, PostgreSQL `UUID`) | Generados por aplicación o `gen_random_uuid()`. Serializados como string RFC 4122 en JSON. |
| **Precios / Moneda** | `Decimal` en **PAB** (`NUMERIC(12, 2)`) | Sin `float`. `currency` por defecto `"PAB"` (`CHAR(3)`). Serializados como string decimal fijo (`"149900.00"`) en JSON para evitar pérdida de precisión. `B/.` es solo símbolo de presentación, nunca código de moneda ni conversión de importes. |
| **Estado de publicación** | Enum explícito `publication_status` | Valores: `draft`, `published`, `archived`. Nunca booleanos implícitos como `is_active` para publicación. |
| **Timestamps** | `TIMESTAMPTZ` en **UTC** | Siempre almacenados en UTC (`DateTime(timezone=True)`). Serializados en ISO-8601 UTC (`2026-11-26T20:00:00Z`). |
| **Cantidades de inventario** | `INTEGER` | `StockBalance.quantity >= 0`. `StockMovement.quantity > 0` acompañado de `direction` (`in` \| `out`). |
| **Idempotencia** | `idempotency_key` (`VARCHAR(128)`) | Obligatorio en comandos de consumo/salida de stock (`out`). Índice único parcial (`WHERE idempotency_key IS NOT NULL`). |
| **Historial persistente en stock cero** | Append-only + fila de saldo persistente | Cuando una variante llega a `quantity = 0`, su fila en `stock_balances` **se conserva** en `0` y todos sus `stock_movements` permanecen inmutables. |

---

## 2. Entidades del Dominio

### 2.1 `Category` (`categories`)
Agrupa productos del catálogo (ej. *Jeans Slim*, *Chaquetas Denim*).

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `name` | `VARCHAR(120)` | `NOT NULL` |
| `slug` | `VARCHAR(140)` | `NOT NULL`, `UNIQUE`, índice |
| `description` | `TEXT` | `NULL` |
| `parent_id` | `UUID` | FK -> `categories.id` (`ON DELETE SET NULL`), `NULL`, índice |
| `display_order` | `INTEGER` | `NOT NULL`, default `0`, `CHECK (display_order >= 0)` |
| `is_active` | `BOOLEAN` | `NOT NULL`, default `true` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |

### 2.2 `Product` (`products`)
Referencia comercial principal del catálogo.

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `category_id` | `UUID` | FK -> `categories.id` (`ON DELETE RESTRICT`), `NOT NULL`, índice |
| `sku` | `VARCHAR(64)` | `NOT NULL`, `UNIQUE` |
| `name` | `VARCHAR(180)` | `NOT NULL` |
| `slug` | `VARCHAR(200)` | `NOT NULL`, `UNIQUE`, índice |
| `description` | `TEXT` | `NULL` |
| `publication_status` | `VARCHAR(20)` | `NOT NULL`, default `'draft'`, `CHECK (publication_status IN ('draft','published','archived'))`, índice |
| `published_at` | `TIMESTAMPTZ` | `NULL`, UTC |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |

### 2.3 `Variant` (`variants`)
Combinación física vendible de un producto por **talla (`size`)** y **color (`color`)**.

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `product_id` | `UUID` | FK -> `products.id` (`ON DELETE CASCADE`), `NOT NULL`, índice |
| `sku` | `VARCHAR(64)` | `NOT NULL`, `UNIQUE` |
| `size` | `VARCHAR(32)` | `NOT NULL` (ej. `28`, `30`, `32`, `S`, `M`, `L`) |
| `color` | `VARCHAR(64)` | `NOT NULL` (ej. `Azul Índigo`, `Negro`) |
| `color_hex` | `VARCHAR(7)` | `NULL`, `CHECK (color_hex IS NULL OR color_hex ~ '^#[0-9A-Fa-f]{6}$')` |
| `barcode` | `VARCHAR(64)` | `NULL`, `UNIQUE` |
| `publication_status` | `VARCHAR(20)` | `NOT NULL`, default `'draft'`, `CHECK (publication_status IN ('draft','published','archived'))` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |

- **Unicidad compuesta:** `UNIQUE (product_id, size, color)` (`uq_variants_product_size_color`).

### 2.4 `Price` (`prices`)
Precio vigente o histórico en **PAB** asociado a una `Variant` (o a nivel `Product` si `variant_id` es nulo).

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `product_id` | `UUID` | FK -> `products.id` (`ON DELETE CASCADE`), `NOT NULL`, índice |
| `variant_id` | `UUID` | FK -> `variants.id` (`ON DELETE CASCADE`), `NULL`, índice |
| `amount_pab` | `NUMERIC(12, 2)` | `NOT NULL`, `CHECK (amount_pab >= 0)` |
| `compare_at_pab` | `NUMERIC(12, 2)` | `NULL`, `CHECK (compare_at_pab IS NULL OR compare_at_pab >= amount_pab)` |
| `currency` | `CHAR(3)` | `NOT NULL`, default `'PAB'`, `CHECK (currency = 'PAB')` |
| `is_current` | `BOOLEAN` | `NOT NULL`, default `true` |
| `valid_from` | `TIMESTAMPTZ` | `NOT NULL`, UTC |
| `valid_to` | `TIMESTAMPTZ` | `NULL`, UTC, `CHECK (valid_to IS NULL OR valid_to > valid_from)` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |

- **Unicidad parcial de precio vigente:**
  - `UNIQUE (product_id) WHERE variant_id IS NULL AND is_current = true`
  - `UNIQUE (variant_id) WHERE variant_id IS NOT NULL AND is_current = true`

### 2.5 `Image` (`images`)
Metadatos de imágenes procesadas con Pillow y almacenadas en `storage/media`.

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `product_id` | `UUID` | FK -> `products.id` (`ON DELETE CASCADE`), `NOT NULL`, índice |
| `variant_id` | `UUID` | FK -> `variants.id` (`ON DELETE SET NULL`), `NULL`, índice |
| `storage_path` | `VARCHAR(512)` | `NOT NULL`, `UNIQUE` (ruta relativa dentro de `MEDIA_ROOT`) |
| `original_filename` | `VARCHAR(255)` | `NOT NULL` |
| `mime_type` | `VARCHAR(64)` | `NOT NULL` (ej. `image/webp`, `image/jpeg`, `image/png`) |
| `size_bytes` | `INTEGER` | `NOT NULL`, `CHECK (size_bytes > 0)` |
| `width` | `INTEGER` | `NOT NULL`, `CHECK (width > 0)` |
| `height` | `INTEGER` | `NOT NULL`, `CHECK (height > 0)` |
| `sha256` | `CHAR(64)` | `NOT NULL`, índice |
| `alt_text` | `VARCHAR(255)` | `NULL` |
| `display_order` | `INTEGER` | `NOT NULL`, default `0`, `CHECK (display_order >= 0)` |
| `is_primary` | `BOOLEAN` | `NOT NULL`, default `false` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |

- **Unicidad parcial:** máximo una imagen primaria por producto (`UNIQUE (product_id) WHERE is_primary = true`).

### 2.6 `StockBalance` (`stock_balances`)
Saldo actual de inventario por `Variant`. **Nunca se elimina cuando llega a `0`.**

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `variant_id` | `UUID` | FK -> `variants.id` (`ON DELETE RESTRICT`), `NOT NULL`, `UNIQUE` |
| `quantity` | `INTEGER` | `NOT NULL`, default `0`, `CHECK (quantity >= 0)` |
| `reserved_quantity` | `INTEGER` | `NOT NULL`, default `0`, `CHECK (reserved_quantity >= 0 AND reserved_quantity <= quantity)` |
| `version` | `INTEGER` | `NOT NULL`, default `1`, `CHECK (version >= 1)` (control optimista complementario a `FOR UPDATE`) |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |

### 2.7 `StockMovement` (`stock_movements`)
Libro mayor **append-only** de movimientos de inventario.

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `variant_id` | `UUID` | FK -> `variants.id` (`ON DELETE RESTRICT`), `NOT NULL`, índice |
| `direction` | `VARCHAR(8)` | `NOT NULL`, `CHECK (direction IN ('in', 'out'))` |
| `movement_type` | `VARCHAR(32)` | `NOT NULL`, `CHECK (movement_type IN ('initial_load','restock','sale','return','adjustment','damage'))` |
| `quantity` | `INTEGER` | `NOT NULL`, `CHECK (quantity > 0)` |
| `quantity_before` | `INTEGER` | `NOT NULL`, `CHECK (quantity_before >= 0)` |
| `quantity_after` | `INTEGER` | `NOT NULL`, `CHECK (quantity_after >= 0)` |
| `idempotency_key` | `VARCHAR(128)` | `NULL`, índice único parcial `WHERE idempotency_key IS NOT NULL` |
| `reference_type` | `VARCHAR(64)` | `NULL` (ej. `order`, `manual_adjustment`, `seed`) |
| `reference_id` | `VARCHAR(128)` | `NULL` |
| `note` | `TEXT` | `NULL` |
| `performed_by` | `UUID` | FK -> `users.id` (`ON DELETE SET NULL`), `NULL`, índice |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC, índice |

- **Invariante aritmética (CHECK en BD):**
  - Si `direction = 'in'`, `quantity_after = quantity_before + quantity`.
  - Si `direction = 'out'`, `quantity_after = quantity_before - quantity`.

### 2.8 `Role` (`roles`)
Roles de autorización RBAC.

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `name` | `VARCHAR(50)` | `NOT NULL`, `UNIQUE` (`admin`, `operator`, `viewer`) |
| `description` | `VARCHAR(255)` | `NULL` |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |

### 2.9 `User` (`users`)
Usuarios administrativos y operativos.

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `role_id` | `UUID` | FK -> `roles.id` (`ON DELETE RESTRICT`), `NOT NULL`, índice |
| `email` | `VARCHAR(255)` | `NOT NULL`, `UNIQUE`, índice |
| `full_name` | `VARCHAR(160)` | `NOT NULL` |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` |
| `is_active` | `BOOLEAN` | `NOT NULL`, default `true` |
| `last_login_at` | `TIMESTAMPTZ` | `NULL`, UTC |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC |

### 2.10 `AuditEvent` (`audit_events`)
Registro inmutable de auditoría para rastrear cambios críticos en catálogo, precios, inventario y usuarios.

| Campo | Tipo SQL / Python | Restricciones |
| --- | --- | --- |
| `id` | `UUID` | PK |
| `actor_user_id` | `UUID` | FK -> `users.id` (`ON DELETE SET NULL`), `NULL`, índice |
| `entity_type` | `VARCHAR(64)` | `NOT NULL`, índice (ej. `product`, `variant`, `price`, `stock_balance`, `user`) |
| `entity_id` | `UUID` | `NOT NULL`, índice |
| `action` | `VARCHAR(64)` | `NOT NULL`, índice (ej. `created`, `updated`, `published`, `archived`, `stock_consumed`, `stock_replenished`) |
| `before_state` | `JSONB` | `NULL` |
| `after_state` | `JSONB` | `NULL` |
| `metadata` | `JSONB` | `NOT NULL`, default `{}` |
| `request_id` | `VARCHAR(128)` | `NULL`, índice |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, UTC, índice |

---

## 3. Diseño Transaccional de Inventario

Todas las mutaciones de inventario deben ejecutarse a través del servicio transaccional (`StockService`):

1. **Validación previa:** `quantity > 0`, `direction in ('in', 'out')`, y si `direction == 'out'` se exige `idempotency_key` no vacío.
2. **Idempotencia:** Dentro de la transacción, consultar `stock_movements` por `idempotency_key`. Si existe:
   - Si coincide `(variant_id, direction, quantity)`, devolver el movimiento existente sin volver a descontar (`idempotent_replay = True`).
   - Si difiere en parámetros, lanzar `IDEMPOTENCY_CONFLICT` (`409`).
3. **Bloqueo pesimista:** Ejecutar `SELECT ... FROM stock_balances WHERE variant_id = :variant_id FOR UPDATE` para serializar concurrencia sobre la misma variante.
4. **Cálculo y verificación:**
   - `direction == 'out'`: verificar `balance.quantity - balance.reserved_quantity >= quantity`. Si no alcanza, lanzar `INSUFFICIENT_STOCK` (`409`) y hacer rollback.
   - Actualizar `balance.quantity`, incrementar `balance.version`, actualizar `balance.updated_at` (UTC).
5. **Persistencia atómica:** Insertar `StockMovement` (con `quantity_before` y `quantity_after`) y `AuditEvent` en la misma transacción.
6. **Stock en cero:** Si `quantity_after == 0`, la fila en `stock_balances` permanece con `quantity = 0` y todo el historial en `stock_movements` se conserva íntegro.

---

## 4. Formas de Comandos y Respuestas (JSON)

### 4.1 Respuesta de Recurso (ejemplo `Product` + `Variant` + `Price` + `StockBalance`)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "category_id": "11111111-1111-4111-8111-111111111111",
  "sku": "JEAN-SLIM-001",
  "name": "Jean Slim Fit Clásico",
  "slug": "jean-slim-fit-clasico",
  "publication_status": "published",
  "published_at": "2026-11-26T20:00:00Z",
  "created_at": "2026-11-26T19:00:00Z",
  "updated_at": "2026-11-26T20:00:00Z"
}
```

### 4.2 Comando de Movimiento de Inventario (`StockMovementCommand`)
```json
{
  "variant_id": "22222222-2222-4222-8222-222222222222",
  "direction": "out",
  "movement_type": "sale",
  "quantity": 2,
  "idempotency_key": "order-2026-0001:variant-2222:1",
  "reference_type": "order",
  "reference_id": "ORD-2026-0001",
  "note": "Venta mostrador"
}
```

### 4.3 Respuesta de Movimiento de Inventario (`StockMovementResult`)
```json
{
  "movement_id": "33333333-3333-4333-8333-333333333333",
  "variant_id": "22222222-2222-4222-8222-222222222222",
  "direction": "out",
  "movement_type": "sale",
  "quantity": 2,
  "quantity_before": 5,
  "quantity_after": 3,
  "idempotency_key": "order-2026-0001:variant-2222:1",
  "idempotent_replay": false,
  "created_at": "2026-11-26T20:05:00Z"
}
```

---

## 5. Semántica de Errores

Todas las respuestas de error en Fase 1+ seguirán un sobre estándar:

```json
{
  "error": {
    "code": "INSUFFICIENT_STOCK",
    "message": "Stock insuficiente para la variante solicitada.",
    "details": {
      "variant_id": "22222222-2222-4222-8222-222222222222",
      "available": 1,
      "requested": 2
    },
    "request_id": "req-abc123"
  }
}
```

| Código de Error | HTTP | Cuándo ocurre |
| --- | --- | --- |
| `VALIDATION_ERROR` | `422` | Violación de esquema, `quantity <= 0`, precio negativo, moneda distinta de `PAB`, estado inválido. |
| `RESOURCE_NOT_FOUND` | `404` | `product_id`, `variant_id`, `category_id` o `user_id` inexistente. |
| `CONFLICT` | `409` | Violación de unicidad (`sku`, `slug`, `email`, `(product_id, size, color)`). |
| `INSUFFICIENT_STOCK` | `409` | Intento de salida (`out`) mayor al stock disponible (`quantity - reserved_quantity`). |
| `IDEMPOTENCY_KEY_REQUIRED` | `422` | Comando de consumo (`out`) sin `idempotency_key`. |
| `IDEMPOTENCY_CONFLICT` | `409` | Reutilización de `idempotency_key` con distinta variante, dirección o cantidad. |
| `UNAUTHORIZED` | `401` | Credenciales inválidas o token ausente/expirado. |
| `FORBIDDEN` | `403` | Rol sin permiso para la operación. |
