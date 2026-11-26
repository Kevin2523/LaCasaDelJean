# Cloudflare Tunnel — `infra/cloudflared`

Configuración de exposición segura sin abrir puertos en el router ni exponer la IP residencial del host Ubuntu.

- **Por defecto (token-managed):** `docker-compose.yml` usa el perfil `tunnel` con `CLOUDFLARE_TUNNEL_TOKEN` definido en `.env`.
- **Alternativa declarativa:** usar `config.example.yml` como base para `config.yml` (ignorado por Git).
- **Regla estricta:** nunca commitear archivos `*.json` de credenciales ni `config.yml` reales.
