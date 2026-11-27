import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

function isProtectedApiRequest(url: string): boolean {
  return (
    url.includes('/api/v1/admin') ||
    url.includes('/api/v1/inventory') ||
    url.includes('/api/v1/auth/me') ||
    url.includes('/api/v1/auth/logout')
  );
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  let outgoing = req;
  if (isProtectedApiRequest(req.url)) {
    const token = auth.getAccessToken();
    if (token) {
      outgoing = req.clone({
        setHeaders: {
          Authorization: `Bearer ${token}`,
        },
      });
    }
  }

  return next(outgoing).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        isProtectedApiRequest(req.url) &&
        !req.url.includes('/api/v1/auth/logout')
      ) {
        auth.handleUnauthorized('Tu sesión ha expirado o fue cerrada. Inicia sesión nuevamente.');
      }
      return throwError(() => error);
    })
  );
};
