# Estrategia de Ramas y Pull Requests

## 1. Ramas Principales

- **`main`**: Rama de producción estable. Protegida: **prohibido** hacer push directo o commits directos. Solo recibe cambios mediante Pull Request desde `develop` (o `hotfix/*` en emergencias).
- **`develop`**: Rama de integración continua para **La Casa del Jean V2**. Toda nueva funcionalidad se integra aquí primero.

## 2. Ramas de Trabajo

Crear siempre desde `develop` actualizado:

- `feat/<fase-o-modulo>-<descripcion>` (ej. `feat/fase1-api-catalogo`)
- `fix/<modulo>-<descripcion>` (ej. `fix/api-pillow-exif`)
- `docs/<tema>` (ej. `docs/actualizar-arquitectura`)
- `chore/<tema>` (ej. `chore/fase0-scaffolding`)

## 3. Flujo de Pull Requests

1. Crear rama de trabajo desde `develop`.
2. Implementar cambios pequeños y verificables (idealmente vinculados a un Issue de GitHub).
3. Verificar localmente (`docker compose config`, linters y tests correspondientes).
4. Abrir PR hacia `develop` (nunca directo a `main` para trabajo regular).
5. Revisión y merge (squash o merge commit limpio según tamaño).
6. Al cerrar una fase completa y validada en `develop`, abrir PR de release `develop -> main`.

## 4. Regla de Convivencia V1 -> V2

- `main` conserva el historial previo del proyecto hasta que `develop` complete las fases requeridas y sea promovido mediante PR revisado.
- No se migra código legado de V1 dentro de `develop`; V2 se construye desde cero sobre esta base limpia.
