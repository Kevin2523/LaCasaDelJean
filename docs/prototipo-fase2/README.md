# Prototipo Visual — Fase 2, Etapa A (`La Casa del Jean`)

Este directorio contiene la **propuesta visual navegable (Etapa A)** para el frontend de **La Casa del Jean V2**, separada intencionalmente de la futura implementación funcional en `apps/web` (Angular + Tailwind).

- **Issues de referencia (sin cerrar):** `#7` (Catálogo Angular responsive), `#8` (Carrito de consultas a WhatsApp), `#9` (Panel administrativo Angular).
- **Alcance:** Solo prototipo estático HTML/CSS/JS con datos simulados (`data.js`). No consume FastAPI, no conecta base de datos, no implementa autenticación real ni activa el flujo real de WhatsApp (`wa.me`).

---

## 1. Decisiones Visuales y de Experiencia

1. **Identidad respetada:** Se mantiene el nombre exacto **La Casa del Jean** como *wordmark* tipográfico limpio, sin introducir un logotipo definitivo ni alterar la identidad de marca.
2. **Estética retail minimalista y familiar (Panamá):**
   - Fondo cálido claro (`#FAF9F6`), tarjetas blancas (`#FFFFFF`) con bordes sutiles (`#E7E5E4`) y acento índigo denim profundo (`#1E3A5F`).
   - Contraste accesible WCAG AA+ para texto principal (`#1C1917`) y secundario (`#57534E`).
   - Tipografía legible de peso moderado (`Inter` con fallback a fuentes del sistema para carga rápida).
3. **Mobile-first y navegación clara:**
   - Cabecera fija con acceso directo a Inicio, Catálogo, Consulta (con contador) y Admin, más menú móvil desplegable (`aria-expanded`).
   - Todas las pantallas requeridas son navegables por interacción y hash URL:
     - `#inicio` — Portada del catálogo (escritorio y móvil)
     - `#catalogo` — Listado, búsqueda, filtros por categoría/talla/orden y estado vacío
     - `#detalle/<id>` — Detalle de prenda con selector de tallas, stock por talla y cantidad
     - `#carrito` — Carrito de consultas con vista previa del mensaje y número referencial `+507 6522-6428` (sin envío real)
     - `#admin-login` — Acceso administrativo simulado con selección de rol
     - `#admin-panel` — Panel de inventario con KPIs, búsqueda, filtro de stock bajo y modales de ajuste/alta con aviso de confirmación
4. **Accesibilidad básica:** Enlace "Saltar al contenido principal", estados `:focus-visible`, roles ARIA en modales/alertas y cierre con tecla `Escape`.

---

## 2. Cómo Abrir el Prototipo Localmente

Desde la raíz del repositorio (o directamente desde `docs/prototipo-fase2`):

### Opción A — Servidor local con Node.js (recomendada)
```powershell
npx --yes serve docs/prototipo-fase2 -l 4173
```
Luego abrir en el navegador: `http://localhost:4173`

### Opción B — Servidor local con Python (si está disponible)
```powershell
python -m http.server 4173 --directory docs/prototipo-fase2
```
Luego abrir en el navegador: `http://localhost:4173`

### Opción C — Apertura directa
También puede abrirse directamente `docs/prototipo-fase2/index.html` en Chrome o Edge.

---

## 3. Atribución de Fotografías (Marcadores de Posición Ilustrativos)

> **Aviso importante:** Todas las fotografías utilizadas en este prototipo son **ilustrativas (marcadores de posición)** con licencia abierta verificable en Wikimedia Commons. No se utilizaron imágenes generadas por IA y serán sustituidas por fotografías reales del inventario de **La Casa del Jean** antes de producción.

| Uso en prototipo | Autor | Licencia | Fuente verificable |
| --- | --- | --- | --- |
| Portada (pila de jeans) | Jcjeansandclothes | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Jeans_Jeans_Jeans.jpg |
| Jean Recto Clásico Índigo | Olgierd Rudak | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Broken_twill_denim_Wrangler_13MWZ_jeans_(2026-01-21).jpg |
| Jean Tiro Alto Silueta Estilizada | Tobias ToMar Maier | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Sedcard_outfit_consisting_of_white_top_(bodysuit),_(blue)_denim_and_heels.jpg |
| Chaqueta Denim Tradicional | NikosLikomitros | CC0 | https://commons.wikimedia.org/wiki/File:Jean_jacket.jpg |
| Camisa Denim Manga Enrollable | May Lee | CC BY-SA 2.0 | https://commons.wikimedia.org/wiki/File:Man_wearing_blue_denim_shirt_with_rolled_sleeves,_tan_chinos_1.jpg |
| Pantalón Chino Algodón Arena | Kuha455405 | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Chino_pants.jpg |
| Conjunto Familiar Rayas y Denim | DimiTalen | CC0 | https://commons.wikimedia.org/wiki/File:Man_in_marini%C3%A8re_with_child.jpg |
| Sobrecamisa Denim Costura Contraste | Shixart1985 | CC BY 2.0 | https://commons.wikimedia.org/wiki/File:Denim_jacket_details.jpg |
| Polo Piqué Clásico Colección Color | Ser Amantio di Nicolao | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Various_colors_of_polo_shirt_at_JCPenney.jpg |
