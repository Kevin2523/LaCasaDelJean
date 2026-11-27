# Prototipo Visual — Fase 2, Etapa A (`La Casa del Jean`)

Este directorio contiene la **propuesta visual editorial navegable (Etapa A, iteración 2)** para **La Casa del Jean V2**, separada intencionalmente de la futura implementación funcional en `apps/web` (Angular + Tailwind).

- **Issues de referencia (sin cerrar):** `#7` (Catálogo Angular responsive), `#8` (Carrito de consultas a WhatsApp), `#9` (Panel administrativo Angular).
- **Alcance:** Solo prototipo estático HTML/CSS/JS con datos simulados (`data.js`). No consume FastAPI, no conecta base de datos, no implementa autenticación JWT ni activa el flujo real de WhatsApp (`wa.me`).
- **Estado:** Propuesta visual pendiente de aprobación humana en Draft PR #21.

---

## 1. Decisiones Visuales y de Experiencia (Iteración 2)

1. **Identidad provisional:** Se conserva el nombre exacto **La Casa del Jean** con una marca tipográfica serif y un motivo sutil de techo en terracota tratados explícitamente como **provisionales (no logotipo definitivo)**.
2. **Paleta y tipografía editorial retail:**
   - Lienzo crema cálido (`#F8F4EE` / `#FDFBF7`), azul denim profundo (`#162D4C`) con textura twill sutil en la barra superior y la barra lateral administrativa, y acento terracota (`#B85A34`).
   - Tipografía serif de moda (`Playfair Display`) para titulares y títulos de producto, combinada con `Inter` para controles, filtros y tablas con contraste accesible WCAG AA+.
3. **Estructura alineada a referencias:**
   - **Inicio (`#inicio`):** Hero editorial denim con parche de colección, fotografía grande, barra de confianza de 4 columnas, 5 tarjetas fotográficas de categoría (`Jeans`, `Damas`, `Caballeros`, `Niños y Familia`, `Básicos`) y destacados.
   - **Catálogo (`#catalogo`):** Filtros laterales por categoría (con conteo), talla y color, búsqueda, ordenamiento y estado vacío. En móvil, cuadrícula de 2 columnas.
   - **Detalle (`#detalle/<id>`):** Galería con miniaturas, precio destacado, badge de disponibilidad, selector de tallas y botones de consulta (vista previa).
   - **Lista de consulta (`#carrito`):** Resumen indicativo, controles de cantidad y vista previa del mensaje para `+507 6522-6428` (sin envío real).
   - **Acceso (`#admin-login`) e Inventario (`#admin-panel`):** Barra lateral denim, 4 tarjetas KPI, tabla con miniaturas/SKU/estado, panel lateral de movimientos recientes y modales de ajuste/alta con aviso de confirmación.
4. **Decisión pendiente de moneda (`B/.` vs `COP`):**
   - La moneda **`B/.`** se mantiene únicamente como **muestra visual** acorde a las referencias de tienda en Panamá.
   - **No está integrada aún** frente al contrato `COP` actual del backend (`apps/api`); su definición oficial queda pendiente antes de la Etapa B.

---

## 2. Cómo Abrir el Prototipo Localmente

```powershell
npx --yes serve docs/prototipo-fase2 -l 4173
```
Abrir en el navegador: `http://localhost:4173` (o abrir directamente `docs/prototipo-fase2/index.html`).

---

## 3. Atribución de Fotografías (Marcadores de Posición Ilustrativos)

> **Aviso importante:** No se utilizaron las capturas de referencia como imágenes del sitio ni imágenes generadas por IA. Todas las fotografías son reales con licencia abierta verificable (Pexels License `https://www.pexels.com/license/` y Wikimedia Commons) y funcionan como marcadores de posición ilustrativos sin implicar aval de la tienda.

| Uso en prototipo | Origen / Autor | Licencia | Fuente verificable |
| --- | --- | --- | --- |
| Hero campaña denim a color | Jcjeansandclothes | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Jeans_Jeans_Jeans.jpg |
| Jean Clásico Índigo / Cat. Jeans | Pexels (#6764017) | Pexels License | https://www.pexels.com/photo/man-in-jean-jacket-and-pants-on-white-backg-6764017/ |
| Jean Tiro Alto Slim | Pexels (#37076315) | Pexels License | https://www.pexels.com/photo/stylish-model-posing-in-casual-denim-and-white-tee-37076315/ |
| Chaqueta Denim Tradicional | NikosLikomitros | CC0 | https://commons.wikimedia.org/wiki/File:Jean_jacket.jpg |
| Categoría Damas | Pexels (#9713293) | Pexels License | https://www.pexels.com/photo/a-woman-wearing-crop-top-and-denim-jeans-9713293/ |
| Colección Denim (panel lateral) | El Nuevo Doge | CC0 | https://commons.wikimedia.org/wiki/File:Jeans_mexicanos.jpg |
| Camisa Denim / Cat. Caballeros | May Lee | CC BY-SA 2.0 | https://commons.wikimedia.org/wiki/File:Man_wearing_blue_denim_shirt_with_rolled_sleeves,_tan_chinos_1.jpg |
| Pantalón Chino Algodón Arena | Kuha455405 | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Chino_pants.jpg |
| Conjunto Familiar / Cat. Niños | DimiTalen | CC0 | https://commons.wikimedia.org/wiki/File:Man_in_marini%C3%A8re_with_child.jpg |
| Sobrecamisa Denim / Cat. Damas | Shixart1985 | CC BY 2.0 | https://commons.wikimedia.org/wiki/File:Denim_jacket_details.jpg |
| Polo Piqué / Cat. Básicos | Ser Amantio di Nicolao | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Various_colors_of_polo_shirt_at_JCPenney.jpg |
