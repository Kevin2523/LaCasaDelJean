import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Subscription } from 'rxjs';
import {
  CategorySummary,
  ProductListItem,
  ProductListQuery,
  ProductSortBy,
} from '../../core/models/catalog.models';
import { CatalogApiService } from '../../core/services/catalog-api.service';
import { ProductCardComponent } from '../../shared/components/product-card/product-card.component';
import { StateBannerComponent } from '../../shared/components/state-banner/state-banner.component';

@Component({
  selector: 'app-catalog-page',
  standalone: true,
  imports: [CommonModule, FormsModule, ProductCardComponent, StateBannerComponent],
  template: `
    <div class="mx-auto max-w-[1240px] px-4 py-8 md:px-7 md:py-10">
      <!-- Page Header -->
      <div class="flex flex-col gap-4 border-b border-border pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
            Catálogo Público · Moneda B/. (PAB)
          </p>
          <h1 class="mt-1 font-editorial text-3xl font-bold text-denim sm:text-4xl">
            {{ activeCategoryName || 'Todas las prendas' }}
          </h1>
          <p class="mt-1 text-sm text-ink-secondary">
            @if (!loading() && !errorMessage()) {
              {{ total() }} {{ total() === 1 ? 'producto encontrado' : 'productos encontrados' }}
            } @else {
              Explora prendas disponibles con filtros por categoría, talla y precio.
            }
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-3">
          <button
            type="button"
            (click)="mobileFiltersOpen.set(!mobileFiltersOpen())"
            [attr.aria-expanded]="mobileFiltersOpen()"
            class="inline-flex items-center gap-2 rounded-lg border border-border-strong bg-surface px-4 py-2 text-sm font-medium text-denim hover:bg-cream-warm lg:hidden"
          >
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75" />
            </svg>
            Filtros
          </button>

          <div class="flex min-w-0 flex-1 items-center gap-2 sm:flex-initial">
            <label for="sort-select" class="shrink-0 text-xs font-medium text-ink-secondary">Ordenar:</label>
            <select
              id="sort-select"
              [(ngModel)]="sortBy"
              (ngModelChange)="applyFilters(1)"
              class="min-w-0 max-w-full flex-1 rounded-lg border border-border-strong bg-white px-2.5 py-2 text-sm text-ink focus:border-denim focus:outline-none sm:flex-initial sm:px-3"
            >
              <option value="newest">Más recientes</option>
              <option value="price_asc">Precio: menor a mayor (B/.)</option>
              <option value="price_desc">Precio: mayor a menor (B/.)</option>
              <option value="name_asc">Nombre: A – Z</option>
              <option value="name_desc">Nombre: Z – A</option>
            </select>
          </div>
        </div>
      </div>

      <div class="mt-8 grid gap-8 lg:grid-cols-12">
        <!-- Filters Sidebar -->
        <aside
          aria-label="Filtros del catálogo"
          class="lg:col-span-3"
          [class.hidden]="!mobileFiltersOpen()"
          [class.lg:block]="true"
        >
          <form
            (ngSubmit)="applyFilters(1)"
            class="space-y-6 rounded-2xl border border-border bg-surface p-5 shadow-[0_2px_8px_rgba(22,45,76,0.04)]"
          >
            <!-- Search -->
            <div>
              <label for="catalog-search" class="block text-xs font-semibold uppercase tracking-[0.12em] text-denim">
                Buscar
              </label>
              <input
                id="catalog-search"
                name="search"
                type="search"
                [(ngModel)]="search"
                placeholder="Nombre, descripción o SKU"
                class="mt-2 w-full rounded-lg border border-border-strong bg-white px-3.5 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-denim focus:outline-none"
              />
            </div>

            <!-- Categories -->
            <div>
              <p class="text-xs font-semibold uppercase tracking-[0.12em] text-denim">Categoría</p>
              <div class="mt-2 space-y-1">
                <button
                  type="button"
                  (click)="selectCategory('')"
                  class="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors"
                  [ngClass]="
                    categorySlug === ''
                      ? 'bg-denim text-white font-semibold'
                      : 'text-ink-secondary hover:bg-cream-warm hover:text-denim'
                  "
                >
                  <span>Todas</span>
                </button>
                @for (cat of categories(); track cat.id) {
                  <button
                    type="button"
                    (click)="selectCategory(cat.slug)"
                    class="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors"
                    [ngClass]="
                      categorySlug === cat.slug
                        ? 'bg-denim text-white font-semibold'
                        : 'text-ink-secondary hover:bg-cream-warm hover:text-denim'
                    "
                  >
                    <span>{{ cat.name }}</span>
                  </button>
                }
              </div>
            </div>

            <!-- Size Chips -->
            <div>
              <p class="text-xs font-semibold uppercase tracking-[0.12em] text-denim">Talla</p>
              <div class="mt-2 flex flex-wrap gap-1.5">
                @for (s of commonSizes; track s) {
                  <button
                    type="button"
                    (click)="toggleSize(s)"
                    class="rounded-lg border px-2.5 py-1.5 text-xs font-semibold transition-colors"
                    [ngClass]="
                      size === s
                        ? 'border-denim bg-denim text-white'
                        : 'border-border-strong bg-white text-ink-secondary hover:border-denim hover:text-denim'
                    "
                  >
                    {{ s }}
                  </button>
                }
              </div>
            </div>

            <!-- Color -->
            <div>
              <label for="catalog-color" class="block text-xs font-semibold uppercase tracking-[0.12em] text-denim">
                Color
              </label>
              <input
                id="catalog-color"
                name="color"
                type="text"
                [(ngModel)]="color"
                placeholder="Ej. Azul Índigo, Negro"
                class="mt-2 w-full rounded-lg border border-border-strong bg-white px-3.5 py-2 text-sm text-ink placeholder:text-ink-muted focus:border-denim focus:outline-none"
              />
            </div>

            <!-- Price Range PAB -->
            <div>
              <p class="text-xs font-semibold uppercase tracking-[0.12em] text-denim">
                Precio en Balboas (B/.)
              </p>
              <div class="mt-2 grid grid-cols-2 gap-2">
                <div>
                  <label for="min-price" class="sr-only">Precio mínimo B/.</label>
                  <input
                    id="min-price"
                    name="minPrice"
                    type="number"
                    min="0"
                    step="0.01"
                    [(ngModel)]="minPricePab"
                    placeholder="Mín B/."
                    class="w-full rounded-lg border border-border-strong bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-muted"
                  />
                </div>
                <div>
                  <label for="max-price" class="sr-only">Precio máximo B/.</label>
                  <input
                    id="max-price"
                    name="maxPrice"
                    type="number"
                    min="0"
                    step="0.01"
                    [(ngModel)]="maxPricePab"
                    placeholder="Máx B/."
                    class="w-full rounded-lg border border-border-strong bg-white px-3 py-2 text-sm text-ink placeholder:text-ink-muted"
                  />
                </div>
              </div>
            </div>

            <!-- In Stock -->
            <label class="flex cursor-pointer items-center gap-2.5 text-sm text-ink">
              <input
                type="checkbox"
                name="inStockOnly"
                [(ngModel)]="inStockOnly"
                (ngModelChange)="applyFilters(1)"
                class="h-4 w-4 rounded border-border-strong accent-denim"
              />
              <span>Solo prendas con stock indicativo</span>
            </label>

            <!-- Actions -->
            <div class="flex flex-col gap-2 pt-2">
              <button
                type="submit"
                class="w-full rounded-full bg-denim px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-denim-deep"
              >
                Aplicar filtros
              </button>
              @if (hasActiveFilters) {
                <button
                  type="button"
                  (click)="clearFilters()"
                  class="w-full rounded-full border border-border-strong bg-white px-4 py-2 text-sm font-medium text-ink-secondary hover:bg-cream-warm hover:text-denim"
                >
                  Limpiar filtros
                </button>
              }
            </div>
          </form>
        </aside>

        <!-- Product Grid Column -->
        <section class="lg:col-span-9" aria-label="Resultados del catálogo">
          @if (loading()) {
            <div class="grid grid-cols-2 gap-4 lg:grid-cols-3" aria-busy="true">
              @for (item of [1, 2, 3, 4, 5, 6]; track item) {
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
          } @else if (errorMessage()) {
            <app-state-banner
              variant="error"
              title="Error al consultar el catálogo"
              [message]="errorMessage()!"
              actionLabel="Reintentar"
              (action)="fetchProducts()"
            />
          } @else if (products().length === 0) {
            <app-state-banner
              variant="empty"
              title="No encontramos prendas con estos filtros"
              message="Prueba ajustando la búsqueda, la talla o el rango de precios en B/. para ver más opciones."
              [actionLabel]="hasActiveFilters ? 'Limpiar filtros' : ''"
              (action)="clearFilters()"
            />
          } @else {
            <div class="grid grid-cols-2 gap-4 lg:grid-cols-3">
              @for (product of products(); track product.id) {
                <app-product-card [product]="product" />
              }
            </div>

            <!-- Pagination -->
            @if (totalPages() > 1) {
              <nav
                aria-label="Paginación de resultados"
                class="mt-10 flex items-center justify-center gap-3"
              >
                <button
                  type="button"
                  [disabled]="page() <= 1"
                  (click)="goToPage(page() - 1)"
                  class="rounded-full border border-border-strong bg-surface px-4 py-2 text-sm font-medium text-denim transition-colors hover:bg-cream-warm disabled:cursor-not-allowed disabled:opacity-40"
                >
                  ← Anterior
                </button>
                <span class="text-sm font-medium text-ink-secondary">
                  Página {{ page() }} de {{ totalPages() }}
                </span>
                <button
                  type="button"
                  [disabled]="page() >= totalPages()"
                  (click)="goToPage(page() + 1)"
                  class="rounded-full border border-border-strong bg-surface px-4 py-2 text-sm font-medium text-denim transition-colors hover:bg-cream-warm disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Siguiente →
                </button>
              </nav>
            }
          }
        </section>
      </div>
    </div>
  `,
})
export class CatalogPageComponent implements OnInit, OnDestroy {
  readonly commonSizes = ['28', '30', '32', '34', '36', 'S', 'M', 'L', 'XL'];
  readonly mobileFiltersOpen = signal(false);
  readonly loading = signal(true);
  readonly errorMessage = signal<string | null>(null);
  readonly categories = signal<CategorySummary[]>([]);
  readonly products = signal<ProductListItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly totalPages = signal(1);

  search = '';
  categorySlug = '';
  size = '';
  color = '';
  minPricePab = '';
  maxPricePab = '';
  inStockOnly = false;
  sortBy: ProductSortBy = 'newest';

  private querySub?: Subscription;

  constructor(
    private readonly catalogApi: CatalogApiService,
    private readonly route: ActivatedRoute,
    private readonly router: Router
  ) {}

  get activeCategoryName(): string | null {
    if (!this.categorySlug) {
      return null;
    }
    return this.categories().find((c) => c.slug === this.categorySlug)?.name ?? null;
  }

  get hasActiveFilters(): boolean {
    return Boolean(
      this.search.trim() ||
        this.categorySlug ||
        this.size ||
        this.color.trim() ||
        this.minPricePab !== '' ||
        this.maxPricePab !== '' ||
        this.inStockOnly
    );
  }

  ngOnInit(): void {
    this.catalogApi.listCategories({ page: 1, page_size: 50 }).subscribe({
      next: (res) => this.categories.set(res.items),
      error: () => {
        // Categories sidebar degrades gracefully if unavailable while main products error shows banner
      },
    });

    this.querySub = this.route.queryParamMap.subscribe((params) => {
      this.search = params.get('search') ?? '';
      this.categorySlug = params.get('categoria') ?? '';
      this.size = params.get('size') ?? '';
      this.color = params.get('color') ?? '';
      this.minPricePab = params.get('min_price_pab') ?? '';
      this.maxPricePab = params.get('max_price_pab') ?? '';
      this.inStockOnly = params.get('in_stock') === 'true';
      const sortParam = params.get('sort_by') as ProductSortBy | null;
      this.sortBy = sortParam ?? 'newest';
      const parsedPage = Number(params.get('page') ?? '1');
      this.page.set(Number.isFinite(parsedPage) && parsedPage >= 1 ? parsedPage : 1);

      this.fetchProducts();
    });
  }

  ngOnDestroy(): void {
    this.querySub?.unsubscribe();
  }

  selectCategory(slug: string): void {
    this.categorySlug = slug;
    this.applyFilters(1);
  }

  toggleSize(selectedSize: string): void {
    this.size = this.size === selectedSize ? '' : selectedSize;
    this.applyFilters(1);
  }

  applyFilters(targetPage = 1): void {
    this.mobileFiltersOpen.set(false);
    const queryParams: Record<string, string | null> = {
      search: this.search.trim() || null,
      categoria: this.categorySlug || null,
      size: this.size || null,
      color: this.color.trim() || null,
      min_price_pab: this.minPricePab !== '' && this.minPricePab !== null ? String(this.minPricePab) : null,
      max_price_pab: this.maxPricePab !== '' && this.maxPricePab !== null ? String(this.maxPricePab) : null,
      in_stock: this.inStockOnly ? 'true' : null,
      sort_by: this.sortBy !== 'newest' ? this.sortBy : null,
      page: targetPage > 1 ? String(targetPage) : null,
    };

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
    });
  }

  clearFilters(): void {
    this.search = '';
    this.categorySlug = '';
    this.size = '';
    this.color = '';
    this.minPricePab = '';
    this.maxPricePab = '';
    this.inStockOnly = false;
    this.sortBy = 'newest';
    this.applyFilters(1);
  }

  goToPage(nextPage: number): void {
    if (nextPage < 1 || nextPage > this.totalPages()) {
      return;
    }
    this.applyFilters(nextPage);
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  fetchProducts(): void {
    this.loading.set(true);
    this.errorMessage.set(null);

    const query: ProductListQuery = {
      page: this.page(),
      page_size: 12,
      category_slug: this.categorySlug || undefined,
      search: this.search.trim() || undefined,
      size: this.size || undefined,
      color: this.color.trim() || undefined,
      min_price_pab: this.minPricePab !== '' ? this.minPricePab : undefined,
      max_price_pab: this.maxPricePab !== '' ? this.maxPricePab : undefined,
      in_stock: this.inStockOnly ? true : undefined,
      sort_by: this.sortBy,
    };

    this.catalogApi.listProducts(query).subscribe({
      next: (res) => {
        this.products.set(res.items);
        this.total.set(res.total);
        this.totalPages.set(Math.max(res.total_pages, 1));
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(this.catalogApi.extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }
}
