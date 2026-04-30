import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';
import { map } from 'rxjs/operators';

/**
 * authGuard — VERSIÓN SEGURA
 *
 * ✅ V-06: La sesión se valida contra el servidor PHP, no solo contra localStorage.
 *
 * ANTES (inseguro):
 *   localStorage.getItem('is_logged') === 'true'
 *   → Bypasseable con: localStorage.setItem('is_logged', 'true')
 *
 * AHORA (seguro):
 *   HTTP GET /check_session.php → verifica la cookie de sesión PHP en el servidor
 *   → Imposible de bypassear desde la consola del navegador
 */
export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.checkSession().pipe(
    map(isValid => {
      if (isValid) {
        return true;
      }
      // Redirigir al home si no hay sesión válida
      return router.createUrlTree(['/']);
    })
  );
};
