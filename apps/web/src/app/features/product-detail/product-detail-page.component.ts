import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { ProductDetail, VariantOut } from '../../core/models/catalog.models';
import { CatalogApiService } from '../../core/services/catalog-api.service';
import { formatPab, getDiscountPercent } from '../../core/utils/format-pab';
import { getPlaceholderPhoto, resolveCatalogImageUrl } from '../../core/utils/media-placeholders';
import { StateBannerComponent } from '../../shared/components/state-banner/state-banner.component';

interface GalleryItem {
  id: string;
  url: string;
  alt: string;
}

@Component({
  selector: 'app-product-detail-page',
  standalone: true,
  imports: [CommonModule, RouterLink, StateBannerComponent],
  template: `
    <div class="mx-auto max-w-[1240px] px-4 py-8 md:px-7 md:py-10">
      @if (loading()) {
        <div class="grid gap-8 md:grid-cols-12" aria-busy="true">
          <div class="aspect-[4/5] animate-pulse rounded-2xl bg-cream-warm md:col-span-6"></div>
          <div class="space-y-4 md:col-span-6">
            <div class="h-4 w-32 animate-pulse rounded bg-cream-warm"></div>
            <div class="h-10 w-3/4 animate-pulse rounded bg-cream-warm"></div>
            <div class="h-8 w-40 animate-pulse rounded bg-cream-warm"></div>
            <div class="h-24 w-full animate-pulse rounded-xl bg-cream-warm"></div>
          </div>
        </div>
      } @else if (errorMessage()) {
        <app-state-banner
          variant="error"
          title="No pudimos cargar este producto"
          [message]="errorMessage()!"
          actionLabel="Reintentar"
          (action)="loadProduct()"
        />
        <div class="mt-6 text-center">
          <a routerLink="/catalogo" class="text-sm font-semibold text-denim hover:text-terracotta hover:underline">
            ← Volver al catálogo
          </a>
        </div>
      } @else {
        @if (product(); as p) {
        <!-- Breadcrumb -->
        <nav aria-label="Ruta de navegación" class="mb-6 flex flex-wrap items-center gap-2 text-xs text-ink-secondary">
          <a routerLink="/" class="hover:text-denim hover:underline">Inicio</a>
          <span aria-hidden="true">/</span>
          <a routerLink="/catalogo" class="hover:text-denim hover:underline">Catálogo</a>
          <span aria-hidden="true">/</span>
          <a
            routerLink="/catalogo"
            [queryParams]="{ categoria: p.category.slug }"
            class="hover:text-denim hover:underline"
          >
            {{ p.category.name }}
          </a>
          <span aria-hidden="true">/</span>
          <span class="font-medium text-denim" aria-current="page">{{ p.name }}</span>
        </nav>

        <div class="grid gap-10 md:grid-cols-12">
          <!-- Gallery Column -->
          <div class="md:col-span-6">
            <div class="overflow-hidden rounded-2xl border border-border bg-cream-warm shadow-sm">
              <img
                [src]="activeImage().url"
                [alt]="activeImage().alt"
                (error)="onImageError($event, p)"
                class="aspect-[4/5] w-full object-cover object-center"
              />
            </div>

            @if (galleryImages().length > 1) {
              <div class="mt-3 grid grid-cols-4 gap-3 sm:grid-cols-5">
                @for (img of galleryImages(); track img.id; let idx = $index) {
                  <button
                    type="button"
                    (click)="selectedImageIndex.set(idx)"
                    [attr.aria-label]="'Ver imagen ' + (idx + 1)"
                    [attr.aria-current]="selectedImageIndex() === idx ? 'true' : null"
                    class="overflow-hidden rounded-xl border-2 transition-all"
                    [ngClass]="
                      selectedImageIndex() === idx
                        ? 'border-terracotta ring-2 ring-terracotta/20'
                        : 'border-border hover:border-denim/40'
                    "
                  >
                    <img
                      [src]="img.url"
                      [alt]="img.alt"
                      (error)="onImageError($event, p)"
                      class="aspect-square w-full object-cover"
                    />
                  </button>
                }
              </div>
            }
          </div>

          <!-- Product Info Column -->
          <div class="md:col-span-6">
            <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
              {{ p.category.name }}
            </p>

            <h1 class="mt-2 font-editorial text-3xl font-bold leading-tight text-denim sm:text-4xl">
              {{ p.name }}
            </h1>

            <p class="mt-2 text-xs font-medium text-ink-muted">
              SKU: <span class="text-ink">{{ selectedVariant()?.sku || p.sku }}</span>
            </p>

            <!-- Price Block -->
            <div class="mt-5 flex flex-wrap items-baseline gap-3">
              <span class="text-3xl font-bold tracking-tight text-denim">
                {{ activePriceFormatted() }}
              </span>
              @if (activeCompareAtFormatted()) {
                <span class="text-base text-ink-muted line-through">
                  {{ activeCompareAtFormatted() }}
                </span>
              }
              @if (activeDiscountPercent()) {
                <span class="rounded-full bg-terracotta px-2.5 py-0.5 text-xs font-semibold text-white">
                  -{{ activeDiscountPercent() }}%
                </span>
              }
            </div>

            <!-- Indicative Stock Status -->
            <div class="mt-4">
              <span
                class="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-semibold"
                [ngClass]="stockBadgeClass()"
              >
                <span class="h-2 w-2 rounded-full bg-current" aria-hidden="true"></span>
                {{ stockLabel() }}
              </span>
              <p class="mt-2 text-xs text-ink-secondary">
                La disponibilidad mostrada es indicativa y se sincroniza con el inventario de tienda.
              </p>
            </div>

            <!-- Variants Selector -->
            @if (p.variants.length > 0) {
              <div class="mt-7 space-y-5 border-t border-border pt-6">
                @if (availableColors().length > 0) {
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-[0.12em] text-denim">
                      Color: <span class="font-normal normal-case text-ink">{{ selectedColor() }}</span>
                    </p>
                    <div class="mt-2.5 flex flex-wrap gap-2">
                      @for (c of availableColors(); track c.name) {
                        <button
                          type="button"
                          (click)="selectColor(c.name)"
                          class="inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors"
                          [ngClass]="
                            selectedColor() === c.name
                              ? 'border-denim bg-denim text-white'
                              : 'border-border-strong bg-white text-ink hover:border-denim'
                          "
                        >
                          @if (c.hex) {
                            <span
                              class="h-3.5 w-3.5 rounded-full border border-black/15"
                              [style.backgroundColor]="c.hex"
                              aria-hidden="true"
                            ></span>
                          }
                          {{ c.name }}
                        </button>
                      }
                    </div>
                  </div>
                }

                <div>
                  <p class="text-xs font-semibold uppercase tracking-[0.12em] text-denim">
                    Talla:
                    <span class="font-normal normal-case text-ink">
                      {{ selectedVariant()?.size || 'Selecciona una talla' }}
                    </span>
                  </p>
                  <div class="mt-2.5 flex flex-wrap gap-2">
                    @for (variant of variantsForSelectedColor(); track variant.id) {
                      <button
                        type="button"
                        (click)="selectVariant(variant)"
                        class="min-w-[48px] rounded-xl border px-3.5 py-2 text-sm font-semibold transition-colors"
                        [ngClass]="
                          selectedVariant()?.id === variant.id
                            ? 'border-denim bg-denim text-white'
                            : variant.stock?.in_stock
                              ? 'border-border-strong bg-white text-denim hover:border-denim'
                              : 'border-border bg-cream-warm text-ink-muted line-through'
                        "
                      >
                        {{ variant.size }}
                      </button>
                    }
                  </div>
                </div>
              </div>
            }

            <!-- Description -->
            <div class="mt-7 border-t border-border pt-6">
              <h2 class="text-xs font-semibold uppercase tracking-[0.14em] text-denim">
                Descripción de la prenda
              </h2>
              <p class="mt-2 text-sm leading-relaxed text-ink-secondary">
                {{ p.description || 'Prenda seleccionada de la colección de La Casa del Jean.' }}
              </p>
            </div>

            <!-- Public Catalog Notice (no cart/checkout in F2-01) -->
            <div class="mt-6 rounded-2xl border border-border bg-surface p-4 text-xs leading-relaxed text-ink-secondary">
              <p class="font-semibold text-denim">Consulta en tienda física</p>
              <p class="mt-1">
                Este catálogo público muestra precios en Balboas (B/.) y disponibilidad indicativa por variante.
                No requiere cuenta de cliente ni realiza cobros en línea.
              </p>
            </div>

            <div class="mt-6">
              <a
                routerLink="/catalogo"
                class="inline-flex items-center gap-2 text-sm font-semibold text-denim hover:text-terracotta hover:underline"
              >
                ← Seguir explorando el catálogo
              </a>
            </div>
          </div>
        </div>
        }
      }
    </div>
  `,
})
export class ProductDetailPageComponent implements OnInit, OnDestroy {
  readonly loading = signal(true);
  readonly errorMessage = signal<string | null>(null);
  readonly product = signal<ProductDetail | null>(null);
  readonly selectedVariant = signal<VariantOut | null>(null);
  readonly selectedColor = signal<string>('');
  readonly selectedImageIndex = signal(0);

  private currentSlug = '';
  private routeSub?: Subscription;

  readonly galleryImages = computed<GalleryItem[]>(() => {
    const p = this.product();
    if (!p) {
      return [];
    }
    if (p.images.length > 0) {
      return [...p.images]
        .sort((a, b) => Number(b.is_primary) - Number(a.is_primary) || a.display_order - b.display_order)
        .map((img) => ({
          id: img.id,
          url: resolveCatalogImageUrl(img.storage_path, `${p.category.slug}-${p.slug}`),
          alt: img.alt_text || p.name,
        }));
    }
    const placeholder = getPlaceholderPhoto(`${p.category.slug}-${p.slug}`);
    return [{ id: 'placeholder', url: placeholder.url, alt: p.name }];
  });

  readonly activeImage = computed<GalleryItem>(() => {
    const list = this.galleryImages();
    return list[this.selectedImageIndex()] ?? list[0] ?? { id: 'empty', url: '', alt: '' };
  });

  readonly availableColors = computed(() => {
    const p = this.product();
    if (!p) {
      return [];
    }
    const seen = new Map<string, string | null>();
    for (const v of p.variants) {
      if (!seen.has(v.color)) {
        seen.set(v.color, v.color_hex);
      }
    }
    return Array.from(seen.entries()).map(([name, hex]) => ({ name, hex }));
  });

  readonly variantsForSelectedColor = computed(() => {
    const p = this.product();
    if (!p) {
      return [];
    }
    const color = this.selectedColor();
    return color ? p.variants.filter((v) => v.color === color) : p.variants;
  });

  readonly activePrice = computed(() => {
    const variantPrice = this.selectedVariant()?.current_price;
    return variantPrice ?? this.product()?.current_price ?? null;
  });

  readonly activePriceFormatted = computed(() =>
    formatPab(this.activePrice()?.amount_pab, this.activePrice()?.currency)
  );

  readonly activeCompareAtFormatted = computed(() => {
    const compareAt = this.activePrice()?.compare_at_pab;
    return compareAt ? formatPab(compareAt, this.activePrice()?.currency) : null;
  });

  readonly activeDiscountPercent = computed(() =>
    getDiscountPercent(this.activePrice()?.amount_pab, this.activePrice()?.compare_at_pab)
  );

  readonly stockLabel = computed(() => {
    const v = this.selectedVariant();
    if (v?.stock) {
      if (!v.stock.in_stock || v.stock.available_quantity <= 0) {
        return 'Agotado temporalmente';
      }
      if (v.stock.available_quantity <= 3) {
        return `Pocas unidades (${v.stock.available_quantity} disp.)`;
      }
      return `Disponible (${v.stock.available_quantity} uds. indicativas)`;
    }
    const p = this.product();
    if (!p || p.variants.length === 0) {
      return 'Consultar disponibilidad';
    }
    const totalAvail = p.variants.reduce((sum, item) => sum + (item.stock?.available_quantity ?? 0), 0);
    return totalAvail > 0 ? `Disponible (${totalAvail} uds. indicativas)` : 'Agotado temporalmente';
  });

  readonly stockBadgeClass = computed(() => {
    const v = this.selectedVariant();
    const qty = v?.stock?.available_quantity ?? 0;
    const inStock = v?.stock?.in_stock ?? false;
    if (!inStock || qty <= 0) {
      return 'bg-[#fee2e2] text-[#991b1b]';
    }
    if (qty <= 3) {
      return 'bg-[#ffedd5] text-[#9a3412]';
    }
    return 'bg-[#dcfce7] text-[#166534]';
  });

  constructor(
    private readonly route: ActivatedRoute,
    private readonly catalogApi: CatalogApiService
  ) {}

  ngOnInit(): void {
    this.routeSub = this.route.paramMap.subscribe((params) => {
      this.currentSlug = params.get('slug') ?? '';
      this.loadProduct();
    });
  }

  ngOnDestroy(): void {
    this.routeSub?.unsubscribe();
  }

  loadProduct(): void {
    if (!this.currentSlug) {
      this.errorMessage.set('No se especificó un producto válido.');
      this.loading.set(false);
      return;
    }

    this.loading.set(true);
    this.errorMessage.set(null);
    this.selectedImageIndex.set(0);

    this.catalogApi.getProductBySlug(this.currentSlug).subscribe({
      next: (detail) => {
        this.product.set(detail);
        const preferredVariant =
          detail.variants.find((v) => v.stock?.in_stock) ?? detail.variants[0] ?? null;
        this.selectedVariant.set(preferredVariant);
        this.selectedColor.set(preferredVariant?.color ?? '');
        this.loading.set(false);
      },
      error: (err) => {
        this.errorMessage.set(this.catalogApi.extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  selectColor(color: string): void {
    this.selectedColor.set(color);
    const matches = this.variantsForSelectedColor();
    const next = matches.find((v) => v.stock?.in_stock) ?? matches[0] ?? null;
    this.selectedVariant.set(next);
  }

  selectVariant(variant: VariantOut): void {
    this.selectedVariant.set(variant);
  }

  onImageError(event: Event, product: ProductDetail): void {
    const img = event.target as HTMLImageElement | null;
    if (!img || img.dataset['fallbackApplied']) {
      return;
    }
    img.dataset['fallbackApplied'] = 'true';
    img.src = getPlaceholderPhoto(`${product.category.slug}-${product.slug}`).url;
  }
}
