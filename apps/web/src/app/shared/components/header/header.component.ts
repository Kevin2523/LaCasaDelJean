import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive],
  template: `
    <a
      href="#contenido-principal"
      class="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-4 focus:z-50 focus:rounded-lg focus:bg-denim focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
    >
      Saltar al contenido principal
    </a>

    <!-- Denim Twill Utility Strip -->
    <div class="denim-twill border-b border-white/10 text-xs text-[#f4efe8]">
      <div class="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-2 px-4 py-2 md:px-7">
        <div class="flex flex-wrap items-center gap-3">
          <span class="font-medium tracking-wide">Panamá · Moneda oficial: B/. (PAB)</span>
          <span class="hidden text-white/40 sm:inline">|</span>
          <span class="hidden sm:inline text-[#e7ddd1]">Stock indicativo en tiempo real desde catálogo</span>
        </div>
        <span class="rounded-full border border-[#f4efe8]/25 bg-terracotta/30 px-2.5 py-0.5 text-[11px] font-medium">
          Identidad provisional · Catálogo público
        </span>
      </div>
    </div>

    <!-- Main Sticky Header -->
    <header class="sticky top-0 z-40 border-b border-border bg-surface/95 backdrop-blur-md">
      <div class="mx-auto flex min-h-[74px] max-w-[1240px] items-center justify-between gap-4 px-4 md:px-7">
        <!-- Provisional Wordmark -->
        <a
          routerLink="/"
          class="group inline-flex flex-col leading-none focus-visible:rounded-md"
          aria-label="La Casa del Jean — Ir al inicio"
        >
          <svg
            class="mb-0.5 h-[11px] w-[56px] text-terracotta transition-transform group-hover:-translate-y-0.5"
            viewBox="0 0 64 14"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M3 12L32 2L61 12"
              stroke="currentColor"
              stroke-width="2.2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <span class="font-editorial text-[1.35rem] font-bold tracking-tight text-denim sm:text-[1.5rem]">
            La Casa del Jean
          </span>
          <span class="mt-0.5 text-[10px] font-medium uppercase tracking-[0.16em] text-ink-secondary">
            Denim &amp; Vestuario
          </span>
        </a>

        <!-- Desktop Nav -->
        <nav aria-label="Navegación principal" class="hidden items-center gap-1 md:flex">
          <a
            routerLink="/"
            routerLinkActive="bg-denim-soft text-denim font-semibold"
            [routerLinkActiveOptions]="{ exact: true }"
            class="rounded-lg px-3.5 py-2 text-sm font-medium text-ink-secondary transition-colors hover:bg-cream-warm hover:text-denim"
          >
            Inicio
          </a>
          <a
            routerLink="/catalogo"
            routerLinkActive="bg-denim-soft text-denim font-semibold"
            class="rounded-lg px-3.5 py-2 text-sm font-medium text-ink-secondary transition-colors hover:bg-cream-warm hover:text-denim"
          >
            Catálogo
          </a>
        </nav>

        <!-- Quick Search (Desktop) -->
        <form
          (ngSubmit)="onSearchSubmit()"
          role="search"
          class="hidden flex-1 max-w-xs items-center lg:flex"
        >
          <label for="header-search" class="sr-only">Buscar prendas</label>
          <div class="relative w-full">
            <input
              id="header-search"
              name="q"
              type="search"
              [(ngModel)]="searchTerm"
              placeholder="Buscar jeans, tallas, SKU..."
              class="w-full rounded-full border border-border-strong bg-white py-2 pl-4 pr-10 text-sm text-ink placeholder:text-ink-muted focus:border-denim focus:outline-none"
            />
            <button
              type="submit"
              aria-label="Buscar en catálogo"
              class="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-ink-secondary hover:bg-cream-warm hover:text-denim"
            >
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="m21 21-4.35-4.35m0 0A7.5 7.5 0 1 0 5.65 5.65a7.5 7.5 0 0 0 11 11Z" />
              </svg>
            </button>
          </div>
        </form>

        <!-- Mobile Menu Button -->
        <button
          type="button"
          (click)="toggleMobileMenu()"
          [attr.aria-expanded]="mobileMenuOpen()"
          aria-controls="mobile-nav"
          aria-label="Abrir menú de navegación"
          class="inline-flex items-center justify-center rounded-lg border border-border bg-white p-2 text-denim hover:bg-cream-warm md:hidden"
        >
          @if (mobileMenuOpen()) {
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          } @else {
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          }
        </button>
      </div>

      <!-- Mobile Navigation Drawer -->
      @if (mobileMenuOpen()) {
        <div id="mobile-nav" class="border-t border-border bg-surface px-4 py-4 md:hidden">
          <form (ngSubmit)="onSearchSubmit()" role="search" class="mb-3">
            <label for="mobile-search" class="sr-only">Buscar prendas</label>
            <div class="flex gap-2">
              <input
                id="mobile-search"
                name="mq"
                type="search"
                [(ngModel)]="searchTerm"
                placeholder="Buscar jeans, color, SKU..."
                class="flex-1 rounded-lg border border-border-strong bg-white px-3.5 py-2 text-sm text-ink placeholder:text-ink-muted"
              />
              <button
                type="submit"
                class="rounded-lg bg-denim px-4 py-2 text-sm font-medium text-white hover:bg-denim-deep"
              >
                Buscar
              </button>
            </div>
          </form>
          <nav aria-label="Navegación móvil" class="flex flex-col gap-1">
            <a
              routerLink="/"
              (click)="closeMobileMenu()"
              routerLinkActive="bg-denim-soft text-denim font-semibold"
              [routerLinkActiveOptions]="{ exact: true }"
              class="rounded-lg px-3 py-2.5 text-sm font-medium text-ink-secondary hover:bg-cream-warm"
            >
              Inicio
            </a>
            <a
              routerLink="/catalogo"
              (click)="closeMobileMenu()"
              routerLinkActive="bg-denim-soft text-denim font-semibold"
              class="rounded-lg px-3 py-2.5 text-sm font-medium text-ink-secondary hover:bg-cream-warm"
            >
              Catálogo completo
            </a>
          </nav>
        </div>
      }
    </header>
  `,
})
export class HeaderComponent {
  readonly mobileMenuOpen = signal(false);
  searchTerm = '';

  constructor(private readonly router: Router) {}

  toggleMobileMenu(): void {
    this.mobileMenuOpen.update((open) => !open);
  }

  closeMobileMenu(): void {
    this.mobileMenuOpen.set(false);
  }

  onSearchSubmit(): void {
    const q = this.searchTerm.trim();
    this.closeMobileMenu();
    this.router.navigate(['/catalogo'], {
      queryParams: q ? { search: q } : {},
    });
  }
}
