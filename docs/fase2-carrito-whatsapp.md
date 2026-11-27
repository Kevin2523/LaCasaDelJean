# Carrito de Consultas a WhatsApp (F2-02 · Issue #8)

## Alcance funcional

El carrito de consultas permite al visitante seleccionar prendas desde el catálogo público (`#7`), elegir talla/variante y cantidad, revisar un resumen con precios indicativos en Balboas (`B/.`, PAB) y generar un enlace `https://wa.me/50765226428?text=...` con el mensaje codificado en porcentaje (`encodeURIComponent`).

**Fuera de alcance por diseño:**
- No crea órdenes ni pedidos en backend.
- No procesa pagos en línea.
- No reserva inventario ni descuenta stock.
- No requiere cuenta de cliente ni autenticación.

## Decisión documentada de persistencia (`localStorage`)

- **Mecanismo:** `window.localStorage` en el navegador del cliente.
- **Clave:** `lcdj_inquiry_cart_v1`
- **Esquema versionado:**
  ```json
  {
    "version": 1,
    "updatedAt": "2026-11-27T18:00:00.000Z",
    "items": [
      {
        "key": "<productId>::<variantId>",
        "productId": "...",
        "productSlug": "...",
        "productName": "...",
        "categorySlug": "...",
        "sku": "...",
        "variantId": "...",
        "size": "32",
        "color": "Índigo",
        "unitPricePab": 39.95,
        "currency": "PAB",
        "quantity": 2,
        "imageUrl": "...",
        "imageAlt": "..."
      }
    ]
  }
  ```
- **Comportamiento:**
  - La lista persiste entre recargas y sesiones del mismo navegador hasta que el usuario elimine artículos o pulse **Vaciar lista**.
  - Agregar la misma combinación de producto + variante acumula la cantidad (máximo `99` unidades por línea).
  - Si `localStorage` no está disponible (modo privado estricto o entorno sin navegador), el servicio degrada limpiamente a estado en memoria sin errores.
  - Si los datos guardados están corruptos o pertenecen a una versión incompatible, la clave se limpia automáticamente y se inicia una lista vacía.

## Configuración del número de WhatsApp

- Por defecto: `50765226428` (`+507 6522-6428`), definido en `environment.whatsappNumber`.
- Sobrescritura en tiempo de ejecución opcional mediante `window.__LCDJ_CONFIG__.whatsappNumber`.
- El enlace generado siempre sanitiza a dígitos y codifica el mensaje con `encodeURIComponent`.
