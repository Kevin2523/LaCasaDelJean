# Plan de Fases — La Casa del Jean V2

## Fase 0 — Base, Gobernanza y Scaffolding (Actual)
- Estructura limpia de monorepo en `develop`.
- `docker-compose.yml` mínimo y seguro optimizado para laptop Ryzen 3 / 8 GB RAM (Ubuntu).
- Dockerfiles placeholder no-root, `.env.example` sin secretos, `.gitignore`, `.dockerignore`.
- Documentación base: arquitectura, seguridad, convenciones, ramas/PRs, fases y ADRs.

## Fase 1 — Núcleo Backend y Catálogo Base
- Inicialización de FastAPI en `apps/api`, SQLAlchemy + Alembic + PostgreSQL.
- Modelos iniciales (productos, categorías, variantes/tallas, inventario, medios).
- Servicio de procesamiento y almacenamiento persistente de imágenes con Pillow en `storage/media`.
- Inicialización de workspace Angular + Tailwind CSS en `apps/web` y vistas base del catálogo.

## Fase 2 — Panel Administrativo y Operación Comercial
- Autenticación y autorización de administradores (JWT + hashing seguro).
- CRUD completo de productos, variantes, precios y carga de imágenes desde `apps/web`.
- Gestión de pedidos/apartados y auditoría básica.

## Fase 3 — Automatización Hermes / MCP / Telegram
- Implementación de `services/hermes` con integración Telegram Bot API y servidor/cliente MCP.
- Lista blanca de chats (`TELEGRAM_ALLOWED_CHAT_IDS`) y autenticación interna con `apps/api`.
- Consultas rápidas de stock, alertas y carga asistida de catálogo.

## Fase 4 — Endurecimiento, Despliegue Ubuntu y Cloudflare Tunnel
- Configuración productiva en Ubuntu (systemd/Docker restart, backups automáticos de PostgreSQL y `storage/media`).
- Activación de Cloudflare Tunnel (`cloudflared`) con dominio propio y políticas de acceso.
- Pruebas de carga/memoria en Ryzen 3 / 8 GB y checklist final de seguridad antes de PR `develop -> main`.
