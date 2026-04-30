import { HttpInterceptorFn } from '@angular/common/http';

/**
 * authInterceptor — Interceptor HTTP de Seguridad
 *
 * ✅ V-08: Añade automáticamente las credenciales de sesión a TODAS las peticiones
 *          hacia el backend PHP, sin tener que modificar cada llamada en api.service.ts
 *
 * El uso de `withCredentials: true` es CRÍTICO para que el navegador envíe las
 * cookies de sesión PHP (PHPSESSID) en las peticiones cross-origin.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // Solo añadir credenciales a peticiones hacia nuestro backend
  const isBackendRequest = req.url.includes('localhost/LaCasaDelJean/backend') ||
                           req.url.includes('tu-dominio-real.com');

  if (isBackendRequest) {
    const authReq = req.clone({
      withCredentials: true // ✅ Envía cookies de sesión PHP automáticamente
    });
    return next(authReq);
  }

  return next(req);
};



