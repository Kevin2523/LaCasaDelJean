# Convenciones del Monorepo — La Casa del Jean V2

## 1. Estructura de Directorios

- `apps/web`: Frontend Angular + Tailwind CSS.
- `apps/api`: Backend FastAPI + Pillow + migraciones Alembic.
- `services/hermes`: Worker Hermes + MCP + Telegram.
- `infra/`: Infraestructura declarativa (`postgres/init`, `cloudflared`).
- `storage/media`: Almacenamiento persistente de imágenes (solo `.gitkeep` versionado).
- `docs/`: Documentación técnica y de gobernanza.

## 2. Convenciones de Código

### Python (`apps/api`, `services/hermes`)
- **Versión:** Python 3.12+.
- **Estilo:** PEP 8, tipado estático obligatorio en firmas públicas (`typing` / Python 3.12 syntax), docstrings concisos.
- **Linter/Formatter:** `ruff` (formato + lint) y `pytest` para pruebas.
- **Configuración:** `pydantic-settings` leyendo variables de entorno.

### TypeScript / Angular / Tailwind (`apps/web`)
- **Componentes:** Standalone components de Angular, señales (`signal`, `computed`) para estado reactivo.
- **Estilos:** Tailwind CSS como primera opción; evitar CSS global innecesario.
- **Tipado:** `strict: true` en `tsconfig.json`, prohibido `any` sin justificación explícita.

### Commits (Conventional Commits)
Formato: `<tipo>(<alcance>): <descripción breve en imperativo>`

Tipos permitidos:
- `feat`: nueva funcionalidad
- `fix`: corrección de error
- `chore`: mantenimiento, scaffolding, dependencias
- `docs`: documentación
- `refactor`: refactorización sin cambio funcional
- `test`: pruebas
- `ci`: pipelines o scripts de automatización
- `sec`: mejoras o parches de seguridad

Ejemplos:
- `chore(fase-0): inicializar scaffolding de monorepo y compose`
- `feat(api): agregar endpoint de carga de imágenes con pillow`
