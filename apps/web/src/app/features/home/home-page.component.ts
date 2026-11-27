import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { CategorySummary, ProductListItem } from '../../core/models/catalog.models';
import { CatalogApiService } from '../../core/services/catalog-api.service';
import { getPlaceholderPhoto, HERO_PHOTO } from '../../core/utils/media-placeholders';
import { ProductCardComponent } from '../../shared/components/product-card/product-card.component';
import { StateBannerComponent } from '../../shared/components/state-banner/state-banner.component';

@Component({
  selector: 'app-home-page',
  standalone: true,
  imports: [CommonModule, RouterLink, ProductCardComponent, StateBannerComponent],
  template: `
    <!-- Editorial Denim Hero -->
    <section class="relative overflow-hidden border-b border-border bg-cream-warm">
      <div class="mx-auto grid max-w-[1240px] items-center gap-8 px-4 py-10 md:grid-cols-12 md:px-7 md:py-16">
        <div class="md:col-span-6 lg:col-span-5">
          <span
            class="inline-flex items-center gap-2 rounded-full border border-terracotta/30 bg-terracotta-soft px-3.5 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-terracotta"
          >
            Colección Denim · Panamá
          </span>

          <h1 class="mt-4 font-editorial text-4xl font-bold leading-[1.12] tracking-tight text-denim sm:text-5xl">
            El calce perfecto en cada prenda denim
          </h1>

          <p class="mt-4 text-base leading-relaxed text-ink-secondary">
            Explora nuestro catálogo público actualizado con precios en Balboas
            (<strong class="font-semibold text-denim">B/.</strong>), variantes por talla y color, y disponibilidad indicativa directamente desde inventario.
          </p>

          <div class="mt-7 flex flex-wrap gap-3">
            <a
              routerLink="/catalogo"
              class="inline-flex items-center justify-center rounded-full bg-denim px-6 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-denim-deep"
            >
              Explorar catálogo
            </a>
            <a
              routerLink="/catalogo"
              [queryParams]="{ in_stock: 'true' }"
              class="inline-flex items-center justify-center rounded-full border border-denim/25 bg-surface px-6 py-3 text-sm font-semibold text-denim transition-colors hover:border-denim hover:bg-denim-soft"
            >
              Ver disponibles hoy
            </a>
          </div>
        </div>

        <div class="md:col-span-6 lg:col-span-7">
          <figure class="relative overflow-hidden rounded-2xl border border-border bg-denim shadow-[0_14px_36px_rgba(22,45,76,0.14)]">
            <img
              [src]="heroPhoto.url"
              [alt]="heroPhoto.alt"
              class="aspect-[16/10] w-full object-cover object-center"
            />
            <figcaption class="flex flex-wrap items-center justify-between gap-2 bg-denim/90 px-4 py-2.5 text-xs text-[#e7ddd1]">
              <span class="font-medium text-white">Selección editorial · Denim clásico y casual</span>
              <span>Foto ilustrativa: {{ heroPhoto.author }} ({{ heroPhoto.license }})</span>
            </figcaption>
          </figure>
        </div>
      </div>
    </section>

    <!-- 4-Column Trust Bar -->
    <section aria-label="Ventajas del catálogo" class="border-b border-border bg-surface">
      <div class="mx-auto grid max-w-[1240px] grid-cols-2 gap-4 px-4 py-6 md:grid-cols-4 md:px-7">
        <div class="flex items-start gap-3">
          <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-denim-soft text-denim font-bold text-sm">
            B/.
          </span>
          <div>
            <p class="text-sm font-semibold text-denim">Precios en Balboas</p>
            <p class="text-xs text-ink-secondary">Moneda oficial PAB clara y transparente.</p>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-terracotta-soft text-terracotta">
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="m4.5 12.75 6 6 9-13.5" />
            </svg>
          </span>
          <div>
            <p class="text-sm font-semibold text-denim">Stock indicativo real</p>
            <p class="text-xs text-ink-secondary">Disponibilidad conectada al inventario.</p>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-denim-soft text-denim">
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z" />
            </svg>
          </span>
          <div>
            <p class="text-sm font-semibold text-denim">Tallas y colores</p>
            <p class="text-xs text-ink-secondary">Filtra por talla, categoría y rango B/.</p>
          </div>
        </div>

        <div class="flex items-start gap-3">
          <span class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-terracotta-soft text-terracotta">
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 21v-7.5a.75.75 0 0 1 .75-.75h3a.75.75 0 0 1 .75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349M3.75 21V9.349m0 0a3.001 3.001 0 0 0 3.75-.615A2.993 2.993 0 0 0 9.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 0 0 2.25 1.016c.896 0 1.7-.393 2.25-1.015a3.001 3.001 0 0 0 3.75.614" />
            </svg>
          </span>
          <div>
            <p class="text-sm font-semibold text-denim">Consulta directa</p>
            <p class="text-xs text-ink-secondary">Sin registros obligatorios ni cuentas.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Main Home Content -->
    <div class="mx-auto max-w-[1240px] px-4 py-12 md:px-7">
      @if (errorMessage()) {
        <app-state-banner
          variant="error"
          title="No pudimos cargar el inicio del catálogo"
          [message]="errorMessage()!"
          actionLabel="Reintentar"
          (action)="loadHomeData()"
        />
      } @else {
        <!-- Categories Section -->
        <section aria-labelledby="home-categories-heading">
          <div class="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
                Explora por línea
              </p>
              <h2 id="home-categories-heading" class="mt-1 font-editorial text-2xl font-bold text-denim sm:text-3xl">
                Categorías destacadas
              </h2>
            </div>
            <a
              routerLink="/catalogo"
              class="text-sm font-semibold text-denim hover:text-terracotta hover:underline"
            >
              Ver todo el catálogo →
            </a>
          </div>

          @if (loading()) {
            <div class="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5" aria-busy="true">
              @for (item of [1, 2, 3, 4, 5]; track item) {
                <div class="aspect-[4/5] animate-pulse rounded-2xl bg-cream-warm"></div>
              }
            </div>
          } @else if (categories().length === 0) {
            <div class="mt-6">
              <app-state-banner
                variant="empty"
                title="Aún no hay categorías publicadas"
                message="Cuando se activen categorías en el catálogo aparecerán aquí automáticamente."
              />
            </div>
          } @else {
            <div class="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              @for (cat of categories(); track cat.id) {
                <a
                  [routerLink]="['/catalogo']"
                  [queryParams]="{ categoria: cat.slug }"
                  class="group relative flex aspect-[4/5] flex-col justify-end overflow-hidden rounded-2xl border border-border bg-denim shadow-sm transition-transform duration-300 hover:-translate-y-1"
                >
                  <img
                    [src]="categoryPhotoUrl(cat)"
                    [alt]="cat.name"
                    loading="lazy"
                    class="absolute inset-0 h-full w-full object-cover object-center transition-transform duration-500 group-hover:scale-105"
                  />
                  <div class="absolute inset-0 bg-gradient-to-t from-denim-deep/90 via-denim/30 to-transparent"></div>
                  <div class="relative z-10 p-4 text-white">
                    <h3 class="font-editorial text-lg font-bold leading-tight">{{ cat.name }}</h3>
                    @if (cat.description) {
                      <p class="mt-1 line-clamp-2 text-xs text-[#e7ddd1]">{{ cat.description }}</p>
                    }
                  </div>
                </a>
              }
            </div>
          }
        </section>

        <!-- Featured Products Section -->
        <section aria-labelledby="home-featured-heading" class="mt-14">
          <div class="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
                Recién publicados
              </p>
              <h2 id="home-featured-heading" class="mt-1 font-editorial text-2xl font-bold text-denim sm:text-3xl">
                Destacados del catálogo
              </h2>
            </div>
            <a
              routerLink="/catalogo"
              class="text-sm font-semibold text-denim hover:text-terracotta hover:underline"
            >
              Explorar todas las prendas →
            </a>
          </div>

          @if (loading()) {
            <div class="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4" aria-busy="true">
              @for (item of [1, 2, 3, 4]; track item) {
                <div class="overflow-hidden rounded-2xl border border-border bg-surface">
                  <div class="aspect-[4/5] animate-pulse bg-cream-warm"></div>
                  <div class="space-y-2 p-4">
                    <div class="h-3 w-20 animate-pulse rounded bg-cream-warm"></div>
                    <div class="h-5 w-3/4 animate-pulse rounded bg-cream-warm"></div>
                    <div class="h-4 w-24 animate-pulse rounded bg-cream-warm"></div>
                  </div>
                </div>
              }
            </div>
          } @else if (featuredProducts().length === 0) {
            <div class="mt-6">
              <app-state-banner
                variant="empty"
                title="Catálogo en preparación"
                message="Todavía no hay productos publicados disponibles para mostrar."
              />
            </div>
          } @else {
            <div class="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
              @for (product of featuredProducts(); track product.id) {
                <app-product-card [product]="product" />
              }
            </div>
          }
        </section>
      }
    </div>
  `,
})
export class HomePageComponent implements OnInit {
  readonly heroPhoto = HERO_PHOTO;
  readonly loading = signal(true);
  readonly errorMessage = signal<string | null>(null);
  readonly categories = signal<CategorySummary[]>([]);
  readonly featuredProducts = signal<ProductListItem[]>([]);

  constructor(private readonly catalogApi: CatalogApiService) {}

  ngOnInit(): void {
    this.loadHomeData();
  }

  loadHomeData(): void {
    this.loading.set(true);
    this.errorMessage.set(null);

    forkJoin({
      categories: this.catalogApi.listCategories({ page: 1, page_size: 10 }),
      products: this.catalogApi.listProducts({ page: 1, page_size: 8, sort_by: 'newest' }),
    }).subscribe({
      next: ({ categories, products }) => {
        this.categories.set(categories.items);
        this.featuredProducts.set(products.items);
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(this.catalogApi.extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  categoryPhotoUrl(category: CategorySummary): string {
    return getPlaceholderPhoto(`${category.slug} ${category.name}`).url;
  }
}
