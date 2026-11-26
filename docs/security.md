# Seguridad — La Casa del Jean V2

## 1. Principios de Diseño

1. **Mínimo privilegio:** todos los contenedores de aplicación (`web`, `api`, `hermes`) se ejecutan con usuarios no-root (`nginx`, `appuser`, `hermesuser`).
2. **Sistema de archivos de solo lectura:** `api`, `web`, `hermes` y `cloudflared` usan `read_only: true` con `tmpfs` estrictamente para rutas temporales (`/tmp`, `/var/cache/nginx`, `/var/run`).
3. **Sin escalada de privilegios:** todos los servicios declaran `security_opt: ["no-new-privileges:true"]`.
4. **Exposición mínima de puertos:**
   - PostgreSQL (`5432`) **no** expone puertos al host y vive en la red `db_internal` (`internal: true`).
   - `web` y `api` solo escuchan en `127.0.0.1` (`127.0.0.1:4200` y `127.0.0.1:8000`), nunca en `0.0.0.0`.
   - La exposición externa se realiza exclusivamente mediante Cloudflare Tunnel (`cloudflared`).

## 2. Gestión de Secretos y Configuración

- `.env` está ignorado en `.gitignore` y `.dockerignore`.
- `.env.example` contiene **únicamente** valores de plantilla (`CHANGE_ME_*`), nunca credenciales reales.
- Los archivos `infra/cloudflared/*.json` y `infra/cloudflared/config.yml` están ignorados por Git.
- Antes de pasar a producción (Fase 4), se debe:
  - Generar `JWT_SECRET_KEY`, `POSTGRES_PASSWORD` y `HERMES_MCP_SHARED_SECRET` con entropía criptográfica (`secrets.token_urlsafe(48)`).
  - Fijar tags/digests inmutables de imágenes base (incluyendo `cloudflared`).
  - Configurar `CORS_ORIGINS` exclusivamente con los dominios HTTPS finales.

## 3. Seguridad de Datos y Media (Fases 1–3)

- **Subida de imágenes (Pillow):** validar tipo MIME real (magic bytes), tamaño máximo (`MAX_UPLOAD_MB`), re-codificar con Pillow eliminando metadatos EXIF y guardar con nombres aleatorios (UUID) en `storage/media`. Nunca confiar en el nombre de archivo del cliente.
- **Telegram / Hermes:** restringir comandos administrativos mediante `TELEGRAM_ALLOWED_CHAT_IDS` (lista blanca explícita) y autenticar llamadas MCP con `HERMES_MCP_SHARED_SECRET`.
- **PostgreSQL:** respaldos periódicos cifrados fuera del contenedor; nunca commitear volcados `.sql` o `.dump` al repositorio.
