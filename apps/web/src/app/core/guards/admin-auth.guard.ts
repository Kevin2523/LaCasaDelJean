import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AdminRole } from '../models/admin.models';
import { AuthService } from '../services/auth.service';

export const adminAuthGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(['/admin/login'], {
    queryParams: { returnUrl: state.url },
  });
};

export const adminGuestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return router.createUrlTree(['/admin/inventario']);
  }

  return true;
};

export function adminRoleGuard(allowedRoles: readonly AdminRole[]): CanActivateFn {
  return (_route, state) => {
    const auth = inject(AuthService);
    const router = inject(Router);

    if (!auth.isAuthenticated()) {
      return router.createUrlTree(['/admin/login'], {
        queryParams: { returnUrl: state.url },
      });
    }

    if (auth.hasAnyRole(allowedRoles)) {
      return true;
    }

    return router.createUrlTree(['/admin/inventario'], {
      queryParams: { denied: '1' },
    });
  };
}
