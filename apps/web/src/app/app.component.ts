import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { FooterComponent } from './shared/components/footer/footer.component';
import { HeaderComponent } from './shared/components/header/header.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, HeaderComponent, FooterComponent],
  template: `
    @if (isAdminRoute()) {
      <router-outlet />
    } @else {
      <div class="flex min-h-screen flex-col overflow-x-clip bg-cream text-ink">
        <app-header />
        <main id="contenido-principal" class="flex-1">
          <router-outlet />
        </main>
        <app-footer />
      </div>
    }
  `,
})
export class AppComponent {
  readonly isAdminRoute = signal(false);

  constructor(private readonly router: Router) {
    this.isAdminRoute.set(this.router.url.startsWith('/admin'));
    this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe((event) => {
        this.isAdminRoute.set(event.urlAfterRedirects.startsWith('/admin'));
      });
  }
}
