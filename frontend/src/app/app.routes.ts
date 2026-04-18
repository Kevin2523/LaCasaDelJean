import { Routes } from '@angular/router';
import { AdminComponent } from './admin/admin';
import { authGuard } from './auth.guard';
import { ClientLayoutComponent } from './client-layout/client-layout';
import { HomeComponent } from './home/home';
import { ShopComponent } from './shop/shop';

export const routes: Routes = [
  {
    path: '',
    component: ClientLayoutComponent,
    children: [
      { path: '', component: HomeComponent },
      { path: 'shop', component: ShopComponent }
    ]
  },
  {
    path: 'admin',
    canActivate: [authGuard],
    component: AdminComponent
  },
  {
    path: '**',
    redirectTo: ''
  }
];
