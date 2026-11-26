# Estrategia de Ramas y Pull Requests

## 1. Ramas Principales

- **`main`**: Rama de producción estable. Protegida: **prohibido** hacer push directo o commits directos. Solo recibe cambios mediante Pull Request desde `develop` (o `hotfix/*` en emergencias).
- **`develop`**: Rama de integración continua para **La Casa del Jean V2**. Toda nueva funcionalidad se integra aquí primero.

## 2. Ramas de Trabajo

Crear siempre desde `develop` actualizado:

- `feature/<fase-o-modulo>-<descripcion>` (ej. `feature/fase1-api-catalogo`)
- `fix/<modulo>-<descripcion>` (ej. `fix/api-pillow-exif`)
- `docs/<tema>` (ej. `docs/actualizar-arquitectura`)
- `chore/<tema>` (ej. `chore/fase0-scaffolding`)

## 3. Flujo de Pull Requests

1. Crear rama de trabajo (`feature/*`, `fix/*`, `docs/*`, `chore/*`) desde `develop`.
2. Implementar cambios pequeños y verificables (vinculados a un Issue de GitHub).
3. Verificar que el workflow de CI (`.github/workflows/ci.yml`) y las validaciones locales pasen (`docker compose --env-file .env.example config --quiet`, linters y tests correspondientes).
4. Abrir PR hacia `develop` (nunca directo a `main` para trabajo regular).
5. Revisión y merge (squash o merge commit limpio según tamaño).
6. **Promoción a `main`:** la apertura de un PR de `develop -> main` se realiza **únicamente con autorización expresa** tras cerrar y validar la fase correspondiente (el despliegue y push de imágenes quedan para Fase 4).

## 4. Regla de Convivencia V1 -> V2

- `main` conserva el historial previo del proyecto hasta que `develop` complete las fases requeridas y sea promovido mediante PR revisado.
- No se migra código legado de V1 dentro de `develop`; V2 se construye desde cero sobre esta base limpia.
