# Arquitectura — La Casa del Jean V2

## 1. Visión General

**La Casa del Jean V2** es una plataforma de comercio y gestión operativa diseñada bajo una arquitectura de monorepo modular con contenedores Docker, pensada para ejecutarse de forma local/autoalojada en un equipo **Ubuntu con procesador AMD Ryzen 3 y 8 GB de RAM**, expuesta de forma segura mediante **Cloudflare Tunnel**.

## 2. Componentes Principales

| Componente | Ruta | Tecnología | Responsabilidad |
| --- | --- | --- | --- |
| Frontend Web | `apps/web` | Angular + Tailwind CSS (Nginx en prod) | Tienda pública y panel administrativo |
| Backend API | `apps/api` | FastAPI + Pydantic + SQLAlchemy/Alembic | Lógica de negocio, autenticación, API REST |
| Procesamiento Media | `apps/api` + `storage/media` | Pillow + volumen persistente | Optimización, redimensionado y almacenamiento de imágenes |
| Base de Datos | `infra/postgres` | PostgreSQL 16 Alpine | Persistencia transaccional |
| Automatización / Bot | `services/hermes` | Hermes + MCP + Telegram Bot API | Flujos conversacionales, notificaciones y herramientas MCP |
| Borde / Túnel | `infra/cloudflared` | Cloudflare Tunnel (`cloudflared`) | Terminación TLS y enrutamiento seguro sin puertos públicos |

## 3. Topología de Red (Docker Compose)

```text
Internet
   │ (TLS via Cloudflare Edge)
   ▼
[cloudflared] ──(app_edge)──► [web :8080]
                      │
                      ├─────► [api :8000] ──(db_internal, internal: true)──► [postgres :5432]
                      │            │
                      │            └──► ./storage/media (bind mount persistente)
                      │
[hermes] ───────(app_edge)─────────┘
   │
   └──(egress HTTPS)──► Telegram Bot API
```

### Aislamiento de Redes
- **`db_internal` (`internal: true`):** conecta únicamente `api` y `postgres`. No tiene salida a internet ni exposición de puertos al host.
- **`app_edge`:** conecta `web`, `api`, `hermes` y `cloudflared`. Los puertos en host (`4200` y `8000`) están enlazados exclusivamente a `127.0.0.1`.

## 4. Presupuesto de Recursos (Host Ryzen 3 / 8 GB RAM)

Para garantizar estabilidad del sistema operativo Ubuntu (y evitar OOM kills), `docker-compose.yml` fija límites explícitos:

- `postgres`: `512M` RAM / `0.75` CPU
- `api`: `768M` RAM / `1.00` CPU
- `web`: `384M` RAM / `0.75` CPU
- `hermes` (perfil `hermes`): `512M` RAM / `0.75` CPU
- `cloudflared` (perfil `tunnel`): `128M` RAM / `0.25` CPU
- **Total máximo asignado a contenedores:** `2.3 GB` RAM (dejando ~5.7 GB para Ubuntu, caché de disco y herramientas locales).
