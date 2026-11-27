import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-admin-shell',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="flex min-h-screen bg-cream text-ink">
      <!-- Mobile Backdrop -->
      @if (mobileSidebarOpen()) {
        <button
          type="button"
          aria-label="Cerrar menú lateral"
          (click)="mobileSidebarOpen.set(false)"
          class="fixed inset-0 z-40 bg-denim-deep/60 lg:hidden"
        ></button>
      }

      <!-- Denim Sidebar -->
      <aside
        [class.translate-x-0]="mobileSidebarOpen()"
        [class.-translate-x-full]="!mobileSidebarOpen()"
        class="denim-twill fixed inset-y-0 left-0 z-50 flex w-68 flex-col justify-between text-[#f4efe8] transition-transform duration-200 lg:static lg:translate-x-0"
      >
        <div>
          <!-- Brand Header -->
          <div class="flex items-center justify-between border-b border-white/10 px-6 py-5">
            <a routerLink="/admin/inventario" class="inline-flex flex-col leading-none">
              <svg class="mb-0.5 h-2.5 w-12 text-terracotta" viewBox="0 0 64 14" fill="none" aria-hidden="true">
                <path d="M3 12L32 2L61 12" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <span class="font-editorial text-lg font-bold tracking-tight text-white">
                La Casa del Jean
              </span>
              <span class="mt-0.5 text-[10px] uppercase tracking-[0.16em] text-[#d5c7b7]">
                Administración
              </span>
            </a>
            <button
              type="button"
              (click)="mobileSidebarOpen.set(false)"
              aria-label="Cerrar navegación"
              class="rounded-lg p-1.5 text-white/80 hover:bg-white/10 lg:hidden"
            >
              ✕
            </button>
          </div>

          <!-- User & Role Card -->
          @if (auth.user(); as currentUser) {
            <div class="mx-4 mt-4 rounded-xl border border-white/15 bg-white/5 p-3.5">
              <p class="truncate text-sm font-semibold text-white">{{ currentUser.full_name }}</p>
              <p class="truncate text-xs text-[#d5c7b7]">{{ currentUser.email }}</p>
              <span
                class="mt-2 inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
                [ngClass]="{
                  'bg-terracotta text-white': currentUser.role === 'admin',
                  'bg-emerald-600/90 text-white': currentUser.role === 'operator',
                  'bg-white/20 text-white': currentUser.role === 'viewer'
                }"
              >
                {{ roleLabel(currentUser.role) }}
              </span>
            </div>
          }

          <!-- Navigation -->
          <nav aria-label="Navegación administrativa" class="mt-5 space-y-1 px-3">
            <a
              routerLink="/admin/inventario"
              (click)="mobileSidebarOpen.set(false)"
              routerLinkActive="bg-white/15 text-white font-semibold"
              class="flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm text-[#e7ddd1] transition-colors hover:bg-white/10 hover:text-white"
            >
              <span>Inventario y Productos</span>
            </a>
            <a
              routerLink="/admin/categorias"
              (click)="mobileSidebarOpen.set(false)"
              routerLinkActive="bg-white/15 text-white font-semibold"
              class="flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm text-[#e7ddd1] transition-colors hover:bg-white/10 hover:text-white"
            >
              <span>Categorías</span>
            </a>
            @if (auth.isAdmin()) {
              <a
                routerLink="/admin/auditoria"
                (click)="mobileSidebarOpen.set(false)"
                routerLinkActive="bg-white/15 text-white font-semibold"
                class="flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm text-[#e7ddd1] transition-colors hover:bg-white/10 hover:text-white"
              >
                <span>Auditoría</span>
              </a>
            }
          </nav>
        </div>

        <!-- Bottom Actions -->
        <div class="space-y-2 border-t border-white/10 p-4">
          <a
            routerLink="/"
            class="block rounded-xl border border-white/15 px-3.5 py-2 text-center text-xs font-medium text-[#e7ddd1] transition-colors hover:bg-white/10 hover:text-white"
          >
            Ver tienda pública
          </a>
          <button
            type="button"
            (click)="onLogout()"
            [disabled]="loggingOut()"
            class="w-full rounded-xl bg-terracotta px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-terracotta-hover disabled:opacity-50"
          >
            {{ loggingOut() ? 'Cerrando sesión...' : 'Cerrar sesión' }}
          </button>
        </div>
      </aside>

      <!-- Main Content Area -->
      <div class="flex min-w-0 flex-1 flex-col">
        <!-- Mobile Top Bar -->
        <header class="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-surface/95 px-4 py-3 backdrop-blur-md lg:hidden">
          <button
            type="button"
            (click)="mobileSidebarOpen.set(true)"
            aria-label="Abrir menú lateral"
            class="rounded-lg border border-border bg-white px-3 py-1.5 text-sm font-medium text-denim"
          >
            ☰ Menú
          </button>
          <span class="font-editorial text-base font-bold text-denim">Panel Admin</span>
          <span class="rounded-full bg-denim-soft px-2.5 py-0.5 text-[11px] font-semibold text-denim">
            {{ auth.role() }}
          </span>
        </header>

        <!-- Role / Access Banners -->
        @if (!auth.canWrite()) {
          <div
            role="status"
            class="border-b border-amber-200 bg-amber-50 px-5 py-2.5 text-xs font-medium text-amber-900"
          >
            Modo solo lectura ({{ roleLabel(auth.role()) }}): puedes consultar productos, existencias e historial, pero las operaciones de edición, publicación y ajuste están restringidas.
          </div>
        }
        @if (deniedNotice()) {
          <div
            role="alert"
            class="flex items-center justify-between border-b border-red-200 bg-red-50 px-5 py-2.5 text-xs font-medium text-red-800"
          >
            <span>No tienes permisos de administrador para acceder a la sección solicitada.</span>
            <button type="button" (click)="deniedNotice.set(false)" class="underline">Cerrar</button>
          </div>
        }

        <main class="flex-1 p-4 sm:p-6 lg:p-8">
          <router-outlet />
        </main>
      </div>
    </div>
  `,
})
export class AdminShellComponent implements OnInit {
  readonly mobileSidebarOpen = signal(false);
  readonly loggingOut = signal(false);
  readonly deniedNotice = signal(false);

  constructor(
    readonly auth: AuthService,
    private readonly route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.auth.verifySession().subscribe();
    this.route.queryParamMap.subscribe((params) => {
      if (params.get('denied') === '1') {
        this.deniedNotice.set(true);
      }
    });
  }

  roleLabel(role: string | null): string {
    switch (role) {
      case 'admin':
        return 'Administrador';
      case 'operator':
        return 'Operador';
      case 'viewer':
        return 'Solo lectura';
      default:
        return 'Usuario';
    }
  }

  onLogout(): void {
    this.loggingOut.set(true);
    this.auth.logout().subscribe({
      complete: () => this.loggingOut.set(false),
    });
  }
}
