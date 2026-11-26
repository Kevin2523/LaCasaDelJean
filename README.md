# La Casa del Jean V2

Monorepo oficial de **La Casa del Jean V2** (Fase 0: scaffolding, configuración base y documentación).

> **Estado actual:** Fase 0 (base técnica y gobernanza). No contiene aún lógica de negocio de Fases 1–4.

## Stack Tecnológico

- **Frontend:** Angular + Tailwind CSS (`apps/web`)
- **Backend API:** FastAPI + PostgreSQL + Pillow (`apps/api`)
- **Base de datos:** PostgreSQL 16 (`infra/postgres`)
- **Automatización / Agentes:** Hermes + MCP + Telegram (`services/hermes`)
- **Almacenamiento persistente:** Volumen local `./storage/media` para imágenes procesadas con Pillow
- **Infraestructura:** Docker Compose sobre Ubuntu Server/Desktop (dimensionado para laptop Ryzen 3 / 8 GB RAM) + Cloudflare Tunnel (`infra/cloudflared`)

## Estructura del Monorepo

```text
.
├── apps/
│   ├── api/                 # Backend FastAPI + Pillow (Fase 1+)
│   └── web/                 # Frontend Angular + Tailwind (Fase 1+)
├── services/
│   └── hermes/              # Worker Hermes / MCP / Telegram (Fase 3+)
├── infra/
│   ├── cloudflared/         # Plantilla y guía de Cloudflare Tunnel
│   └── postgres/init/       # Scripts SQL iniciales (solo bootstrapping)
├── storage/
│   └── media/               # Almacenamiento persistente de imágenes
├── docs/                    # Arquitectura, seguridad, convenciones, ramas, fases y decisiones
├── docker-compose.yml       # Orquestación mínima y segura (Ryzen 3 / 8 GB)
├── .env.example             # Plantilla de variables sin secretos
└── .gitignore
```

## Inicio Rápido (Validación de Fase 0)

1. Copiar variables de entorno de ejemplo:
   ```bash
   cp .env.example .env
   ```
2. Validar la configuración de Docker Compose:
   ```bash
   docker compose --env-file .env.example config
   ```
3. (Opcional) Validar incluyendo perfiles `hermes` y `tunnel`:
   ```bash
   docker compose --env-file .env.example --profile hermes --profile tunnel config
   ```

## Documentación

- [Arquitectura](docs/architecture.md)
- [Seguridad](docs/security.md)
- [Convenciones](docs/conventions.md)
- [Estrategia de Ramas y PRs](docs/branching-and-prs.md)
- [Plan de Fases](docs/phases.md)
- [Registro de Decisiones (ADR)](docs/decisions.md)
