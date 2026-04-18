import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

export const authGuard: CanActivateFn = () => {
  const router = inject(Router);
  const isLogged = typeof localStorage !== 'undefined' && localStorage.getItem('is_logged') === 'true';

  if (isLogged) {
    return true;
  }

  return router.createUrlTree(['/']);
};

