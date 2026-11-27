import { Routes } from '@angular/router';

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
    path: '**',
    redirectTo: '',
  },
];
