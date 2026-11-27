# Backend API — `apps/api`

Servicio API de **La Casa del Jean V2** sobre **FastAPI**, **PostgreSQL** y **SQLAlchemy 2 / Alembic**.

## Endpoints Fase 1 (Issue #5 — F1-02)

### Públicos (solo lectura, `publication_status = 'published'` y categorías activas)
- `GET /health`
- `GET /api/v1/categories` (paginación, `parent_id`, `search`)
- `GET /api/v1/categories/{category_id}` y `GET /api/v1/categories/slug/{slug}`
- `GET /api/v1/products` (paginación, `category_id`, `category_slug`, `search`, `size`, `color`, `in_stock`, `min_price_pab`, `max_price_pab`, `sort_by`)
- `GET /api/v1/products/{product_id}` y `GET /api/v1/products/slug/{slug}`

Los precios usan la moneda oficial `PAB` (balboa panameño). La API recibe y devuelve
`amount_pab`, `compare_at_pab` y `currency: "PAB"`; los filtros públicos son
`min_price_pab` y `max_price_pab`. Los importes JSON conservan dos decimales como
strings. `B/.` es solo el símbolo de presentación de la interfaz; la migración
`20261127_0003` cambia la etiqueta de moneda de los registros existentes sin
convertir sus valores numéricos.

### Protegidos (Catálogo Admin e Inventario)
- `POST /api/v1/admin/categories`, `PATCH /api/v1/admin/categories/{category_id}`
- `POST /api/v1/admin/products`, `GET /api/v1/admin/products/{product_id}`, `PATCH /api/v1/admin/products/{product_id}`
- `POST /api/v1/admin/products/{product_id}/variants`, `PATCH /api/v1/admin/variants/{variant_id}`
- `POST /api/v1/admin/products/{product_id}/prices`
- `POST /api/v1/admin/products/{product_id}/images`, `PATCH /api/v1/admin/images/{image_id}`, `DELETE /api/v1/admin/images/{image_id}`
- `POST /api/v1/inventory/movements` (ajustes atómicos y consumo idempotente vía `StockService`)
- `GET /api/v1/inventory/variants/{variant_id}/balance`
- `GET /api/v1/inventory/variants/{variant_id}/movements`

## Capa de servicios reutilizable (futuro MCP)
- `app/services/catalog.py`: operaciones de consulta pública y mutación de catálogo sobre `Session`.
- `app/services/inventory.py` y `app/services/stock.py`: movimientos atómicos con `SELECT ... FOR UPDATE`, idempotencia y saldo persistente en cero.

## Punto de integración de Autenticación y RBAC (Issue #6)
Todas las rutas de escritura e inventario dependen de `app.api.dependencies.require_write_access`.

Hasta que se integre el Issue #6:
- `require_write_access` es **fail-closed** y responde `401 UNAUTHORIZED` con el sobre de error estándar de `docs/fase1-data-contracts.md`.
- En el Issue #6, reemplazar el cuerpo de `require_write_access` para validar el JWT Bearer, cargar `User` + `Role` activos desde PostgreSQL, exigir rol `admin` u `operator` (`403 FORBIDDEN` para `viewer`) y retornar `AuthenticatedActor`.
