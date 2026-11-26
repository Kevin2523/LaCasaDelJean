# ==============================================================================
# Fase 0 Placeholder Dockerfile - Frontend (Angular + Tailwind -> Nginx)
# La aplicación Angular completa se inicializará en Fase 1.
# ==============================================================================
FROM nginx:1.27-alpine

# Ejecutar nginx sin privilegios en puerto 8080 (compatible con read_only + non-root)
RUN sed -i 's/listen\s*80;/listen 8080;/g' /etc/nginx/conf.d/default.conf \
    && chown -R nginx:nginx /var/cache/nginx /var/log/nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R nginx:nginx /var/run/nginx.pid

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
