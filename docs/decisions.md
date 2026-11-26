# Registro de Decisiones de Arquitectura (ADR)

## ADR-001: Reconstrucción limpia en `develop` sin migración de V1
- **Estado:** Aceptada (Fase 0).
- **Contexto:** La versión anterior mezclaba scripts, SQL suelto y estructura heredada incompatible con la arquitectura objetivo.
- **Decisión:** Sustituir el contenido en `develop` (partiendo desde `origin/main`) por un monorepo limpio sin migrar código V1, manteniendo `main` intacto hasta el release de V2.
- **Consecuencia:** Cero deuda técnica heredada en `develop`; el historial en `main` permanece intacto.

## ADR-002: Monorepo con `apps/` y `services/` + Docker Compose
- **Estado:** Aceptada (Fase 0).
- **Contexto:** Se requiere coordinar Angular/Tailwind, FastAPI/Pillow, PostgreSQL, Hermes/MCP/Telegram y Cloudflare Tunnel en un único servidor Ubuntu local.
- **Decisión:** Usar un monorepo único orquestado por `docker-compose.yml` con perfiles opcionales (`hermes`, `tunnel`) para activar solo lo necesario en cada fase.
- **Consecuencia:** Despliegue reproducible, menor sobrecarga operativa y consumo controlado en hardware de 8 GB RAM.

## ADR-003: Límites estrictos de recursos y seguridad por defecto en Compose
- **Estado:** Aceptada (Fase 0).
- **Contexto:** El host objetivo es una laptop Ubuntu con Ryzen 3 y 8 GB de RAM, sin IP pública fija.
- **Decisión:** Limitar memoria/CPU por servicio (~2.3 GB totales), usar usuarios no-root, `read_only: true`, `no-new-privileges:true`, red `db_internal` aislada (`internal: true`), puertos enlazados a `127.0.0.1` y exposición externa solo vía Cloudflare Tunnel.
- **Consecuencia:** Reduce superficie de ataque y previene agotamiento de memoria en el host.

## ADR-004: Almacenamiento local persistente con Pillow
- **Estado:** Aceptada (Fase 0).
- **Contexto:** El catálogo requiere gestión de imágenes sin depender de buckets S3 externos en Fase 0–2.
- **Decisión:** Montar `./storage/media` en `apps/api` (`/app/storage/media`) y procesar/normalizar imágenes con Pillow.
- **Consecuencia:** Simplicidad operativa y cero costos cloud; requiere incluir `storage/media` en la estrategia de respaldos de Fase 4.
