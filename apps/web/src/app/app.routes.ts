import { Routes } from '@angular/router';
import {
  adminAuthGuard,
  adminGuestGuard,
  adminRoleGuard,
} from './core/guards/admin-auth.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/home/home-page.component').then((m) => m.HomePageComponent),
    title: 'La Casa del Jean — Inicio',
  },
  {
    path: 'catalogo',
    loadComponent: () =>
      import('./features/catalog/catalog-page.component').then((m) => m.CatalogPageComponent),
    title: 'Catálogo — La Casa del Jean',
  },
  {
    path: 'producto/:slug',
    loadComponent: () =>
      import('./features/product-detail/product-detail-page.component').then(
        (m) => m.ProductDetailPageComponent
      ),
    title: 'Detalle de Producto — La Casa del Jean',
  },
  {
    path: 'carrito',
    loadComponent: () =>
      import('./features/inquiry-cart/inquiry-cart-page.component').then(
        (m) => m.InquiryCartPageComponent
      ),
    title: 'Lista de Consulta — La Casa del Jean',
  },
  {
    path: 'consulta',
    redirectTo: 'carrito',
    pathMatch: 'full',
  },
  {
    path: 'admin/login',
    canActivate: [adminGuestGuard],
    loadComponent: () =>
      import('./features/admin/admin-login/admin-login-page.component').then(
        (m) => m.AdminLoginPageComponent
      ),
    title: 'Acceso Administrativo — La Casa del Jean',
  },
  {
    path: 'admin',
    canActivate: [adminAuthGuard],
    loadComponent: () =>
      import('./features/admin/layout/admin-shell.component').then((m) => m.AdminShellComponent),
    children: [
      {
        path: '',
        redirectTo: 'inventario',
        pathMatch: 'full',
      },
      {
        path: 'inventario',
        loadComponent: () =>
          import('./features/admin/inventory/admin-inventory-page.component').then(
            (m) => m.AdminInventoryPageComponent
          ),
        title: 'Inventario — Panel Admin',
      },
      {
        path: 'productos/:id',
        loadComponent: () =>
          import('./features/admin/product-editor/admin-product-editor-page.component').then(
            (m) => m.AdminProductEditorPageComponent
          ),
        title: 'Gestionar Producto — Panel Admin',
      },
      {
        path: 'categorias',
        loadComponent: () =>
          import('./features/admin/categories/admin-categories-page.component').then(
            (m) => m.AdminCategoriesPageComponent
          ),
        title: 'Categorías — Panel Admin',
      },
      {
        path: 'auditoria',
        canActivate: [adminRoleGuard(['admin'])],
        loadComponent: () =>
          import('./features/admin/audit/admin-audit-page.component').then(
            (m) => m.AdminAuditPageComponent
          ),
        title: 'Auditoría — Panel Admin',
      },
    ],
  },
  {
    path: '**',
    redirectTo: '',
  },
];
