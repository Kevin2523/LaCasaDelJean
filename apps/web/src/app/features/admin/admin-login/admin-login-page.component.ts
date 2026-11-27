import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AdminApiService } from '../../../core/services/admin-api.service';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-admin-login-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="flex min-h-screen flex-col bg-cream text-ink lg:flex-row">
      <!-- Denim Brand Panel -->
      <aside class="denim-twill flex flex-col justify-between p-8 text-[#f4efe8] lg:w-[420px] lg:p-12">
        <div>
          <a routerLink="/" class="inline-flex flex-col leading-none">
            <svg class="mb-1 h-3 w-14 text-terracotta" viewBox="0 0 64 14" fill="none" aria-hidden="true">
              <path d="M3 12L32 2L61 12" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span class="font-editorial text-2xl font-bold tracking-tight text-white">
              La Casa del Jean
            </span>
            <span class="mt-1 text-[11px] font-medium uppercase tracking-[0.18em] text-[#d5c7b7]">
              Panel Administrativo
            </span>
          </a>

          <div class="mt-10 space-y-4">
            <h1 class="font-editorial text-3xl font-bold leading-tight text-white">
              Gestión de catálogo e inventario en tiempo real.
            </h1>
            <p class="text-sm leading-relaxed text-[#e7ddd1]/90">
              Acceso protegido con sesiones JWT revocables y control de permisos por rol
              (Administrador, Operador y Solo Lectura). Moneda oficial: Balboa Panameño (B/. PAB).
            </p>
          </div>
        </div>

        <div class="mt-8 border-t border-white/15 pt-5 text-xs text-[#d5c7b7]">
          <a routerLink="/" class="inline-flex items-center gap-1.5 font-medium text-white hover:underline">
            ← Volver al catálogo público
          </a>
        </div>
      </aside>

      <!-- Login Form -->
      <main class="flex flex-1 items-center justify-center p-6 sm:p-10">
        <div class="w-full max-w-md rounded-2xl border border-border bg-surface p-7 shadow-sm sm:p-9">
          <div class="mb-6">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
              Acceso autorizado
            </p>
            <h2 class="mt-1 font-editorial text-2xl font-bold text-denim">
              Iniciar sesión
            </h2>
            <p class="mt-1 text-sm text-ink-secondary">
              Ingresa tus credenciales de personal para administrar productos y existencias.
            </p>
          </div>

          @if (auth.sessionExpiredNotice(); as notice) {
            <div
              role="status"
              class="mb-5 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
            >
              {{ notice }}
            </div>
          }

          @if (errorMessage(); as error) {
            <div
              role="alert"
              class="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              {{ error }}
            </div>
          }

          <form (ngSubmit)="onSubmit()" #loginForm="ngForm" class="space-y-4" novalidate>
            <div>
              <label for="admin-email" class="mb-1.5 block text-sm font-medium text-denim">
                Correo electrónico
              </label>
              <input
                id="admin-email"
                name="email"
                type="email"
                required
                email
                autocomplete="username"
                [(ngModel)]="email"
                #emailModel="ngModel"
                placeholder="admin@lacasadeljean.local"
                class="w-full rounded-xl border border-border-strong bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-ink-muted focus:border-denim focus:outline-none"
              />
              @if (emailModel.invalid && (emailModel.dirty || emailModel.touched)) {
                <p class="mt-1 text-xs text-red-700">Ingresa un correo electrónico válido.</p>
              }
            </div>

            <div>
              <label for="admin-password" class="mb-1.5 block text-sm font-medium text-denim">
                Contraseña
              </label>
              <input
                id="admin-password"
                name="password"
                type="password"
                required
                autocomplete="current-password"
                [(ngModel)]="password"
                #passwordModel="ngModel"
                placeholder="••••••••••••"
                class="w-full rounded-xl border border-border-strong bg-white px-3.5 py-2.5 text-sm text-ink placeholder:text-ink-muted focus:border-denim focus:outline-none"
              />
              @if (passwordModel.invalid && (passwordModel.dirty || passwordModel.touched)) {
                <p class="mt-1 text-xs text-red-700">La contraseña es obligatoria.</p>
              }
            </div>

            <button
              type="submit"
              [disabled]="submitting() || loginForm.invalid"
              class="mt-2 w-full rounded-xl bg-denim px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-denim-deep disabled:cursor-not-allowed disabled:opacity-50"
            >
              {{ submitting() ? 'Verificando credenciales...' : 'Entrar al panel' }}
            </button>
          </form>
        </div>
      </main>
    </div>
  `,
})
export class AdminLoginPageComponent {
  email = '';
  password = '';
  readonly submitting = signal(false);
  readonly errorMessage = signal<string | null>(null);

  constructor(
    readonly auth: AuthService,
    private readonly adminApi: AdminApiService,
    private readonly router: Router,
    private readonly route: ActivatedRoute
  ) {}

  onSubmit(): void {
    if (!this.email.trim() || !this.password) {
      this.errorMessage.set('Completa tu correo electrónico y contraseña.');
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);

    this.auth
      .login({
        email: this.email.trim(),
        password: this.password,
      })
      .subscribe({
        next: () => {
          this.submitting.set(false);
          const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
          const target = returnUrl && returnUrl.startsWith('/admin') ? returnUrl : '/admin/inventario';
          void this.router.navigateByUrl(target);
        },
        error: (err: unknown) => {
          this.submitting.set(false);
          this.errorMessage.set(this.adminApi.extractErrorMessage(err));
        },
      });
  }
}
