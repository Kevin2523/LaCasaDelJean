# Frontend Público — `apps/web` (`La Casa del Jean V2`)

Aplicación web pública construida con **Angular 19** (standalone components) y **Tailwind CSS v4**, alineada con la dirección editorial aprobada en `docs/prototipo-fase2` (Issue `#7` / `F2-01`).

## Características implementadas (F2-01)

- **Identidad visual editorial (provisional):** Paleta crema cálido (`#F8F4EE` / `#FDFBF7`), azul denim profundo (`#162D4C`) con textura twill, acento terracota (`#B85A34`), titulares serif (`Playfair Display`) y cuerpo `Inter`.
- **Rutas públicas:**
  - `/` — Inicio editorial con hero, barra de confianza, tarjetas de categorías reales y productos destacados.
  - `/catalogo` — Cuadrícula responsive (2 columnas en móvil, 3 en escritorio) con búsqueda, filtros por categoría, talla, color, rango de precios en **Balboas (`B/.` · `PAB`)**, filtro de stock indicativo, ordenamiento y paginación sincronizados con la URL.
  - `/producto/:slug` — Detalle de producto con galería de imágenes, precio en `B/.`, selector de variantes por color/talla, SKU dinámico y disponibilidad indicativa.
- **Estados completos:** Skeleton loaders de carga, estados vacíos con acción de limpieza de filtros y estados de error con botón de reintento.
- **Integración real con FastAPI:** Consume exclusivamente los endpoints públicos `/api/v1/categories`, `/api/v1/products`, `/api/v1/products/slug/{slug}` con contratos tipados en TypeScript (`amount_pab`, `compare_at_pab`, `currency: "PAB"`).
- **Alcance controlado:** Sin cuentas de cliente, sin pagos en línea, sin carrito WhatsApp (`#8`) ni panel administrativo (`#9`) todavía.

## Configuración de URL de API

- Por defecto usa rutas relativas (`/api/v1/...`), compatibles con:
  - `ng serve` mediante `proxy.conf.json` -> `http://127.0.0.1:8000`
  - Docker Compose mediante `nginx.conf` -> `http://api:8000`
- Se puede sobreescribir en tiempo de ejecución definiendo `window.__LCDJ_CONFIG__ = { apiBaseUrl: 'https://...' }`.

## Desarrollo local y pruebas

```bash
cd apps/web
npm install
npm start       # http://localhost:4200 (proxy /api -> http://127.0.0.1:8000)
npm run build   # Build de producción en dist/web/browser
npm test -- --watch=false --browsers=ChromeHeadless
```

## Atribución de fotografías ilustrativas

Cuando una prenda o categoría no dispone aún de imagen propia alojada, se utilizan fotografías reales con licencia abierta verificable (Pexels License y Wikimedia Commons CC0 / CC BY-SA), listadas en `src/app/core/utils/media-placeholders.ts` y en el pie de página de la aplicación.
