import { CommonModule } from '@angular/common';
import { Component, Inject, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { WHATSAPP_NUMBER } from '../../core/config/api-config';
import { ProductDetail, VariantOut } from '../../core/models/catalog.models';
import { INQUIRY_CART_MAX_QUANTITY } from '../../core/models/inquiry-cart.models';
import { CatalogApiService } from '../../core/services/catalog-api.service';
import { InquiryCartService } from '../../core/services/inquiry-cart.service';
import { formatPab, getDiscountPercent } from '../../core/utils/format-pab';
import { getPlaceholderPhoto, resolveCatalogImageUrl } from '../../core/utils/media-placeholders';
import { buildWhatsappInquiryUrl } from '../../core/utils/whatsapp-link';
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

            <!-- Quantity & Inquiry Cart Actions -->
            <div class="mt-7 space-y-4 border-t border-border pt-6">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <span class="text-xs font-semibold uppercase tracking-[0.12em] text-denim">
                  Cantidad a consultar
                </span>
                <div class="inline-flex items-center rounded-xl border border-border-strong bg-white">
                  <button
                    type="button"
                    (click)="decrementQuantity()"
                    [disabled]="selectedQuantity() <= 1"
                    aria-label="Disminuir cantidad"
                    class="flex h-10 w-10 items-center justify-center text-base font-semibold text-denim transition-colors hover:bg-cream-warm disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    −
                  </button>
                  <span
                    class="min-w-[2.5rem] text-center text-sm font-semibold text-ink"
                    [attr.aria-label]="'Cantidad seleccionada: ' + selectedQuantity()"
                  >
                    {{ selectedQuantity() }}
                  </span>
                  <button
                    type="button"
                    (click)="incrementQuantity()"
                    [disabled]="selectedQuantity() >= maxQuantity"
                    aria-label="Aumentar cantidad"
                    class="flex h-10 w-10 items-center justify-center text-base font-semibold text-denim transition-colors hover:bg-cream-warm disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    +
                  </button>
                </div>
              </div>

              <div class="grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  (click)="addToInquiryCart()"
                  [disabled]="!canAddToCart()"
                  class="inline-flex items-center justify-center gap-2 rounded-xl bg-denim px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-denim-deep disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Agregar a lista de consulta
                </button>

                <a
                  [href]="directWhatsappUrl()"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center justify-center gap-2 rounded-xl bg-[#1f8b4c] px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#16773f]"
                >
                  Consultar por WhatsApp
                </a>
              </div>

              @if (addedFeedback()) {
                <div
                  role="status"
                  aria-live="polite"
                  class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#166534]/20 bg-[#dcfce7] px-4 py-3 text-xs text-[#166534]"
                >
                  <span class="font-medium">{{ addedFeedback() }}</span>
                  <a
                    routerLink="/carrito"
                    class="font-semibold underline hover:text-denim"
                  >
                    Ver lista de consulta ({{ cart.totalUnits() }}) →
                  </a>
                </div>
              }
            </div>

            <!-- Description -->
            <div class="mt-7 border-t border-border pt-6">
              <h2 class="text-xs font-semibold uppercase tracking-[0.14em] text-denim">
                Descripción de la prenda
              </h2>
              <p class="mt-2 text-sm leading-relaxed text-ink-secondary">
                {{ p.description || 'Prenda seleccionada de la colección de La Casa del Jean.' }}
              </p>
            </div>

            <!-- Public Catalog Inquiry Notice -->
            <div class="mt-6 rounded-2xl border border-border bg-surface p-4 text-xs leading-relaxed text-ink-secondary">
              <p class="font-semibold text-denim">Consulta en tienda física o por WhatsApp</p>
              <p class="mt-1">
                Este catálogo público muestra precios indicativos en Balboas (B/.) y disponibilidad referencial por variante.
                No requiere cuenta de cliente, no reserva stock ni realiza cobros en línea.
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
  readonly selectedQuantity = signal(1);
  readonly addedFeedback = signal<string | null>(null);
  readonly maxQuantity = INQUIRY_CART_MAX_QUANTITY;

  readonly canAddToCart = computed(() => {
    const p = this.product();
    if (!p) {
      return false;
    }
    return p.variants.length === 0 || this.selectedVariant() !== null;
  });

  readonly directWhatsappUrl = computed(() => {
    const p = this.product();
    if (!p) {
      return buildWhatsappInquiryUrl([], this.whatsappNumber);
    }
    const v = this.selectedVariant();
    const price = this.activePrice();
    const numericPrice =
      price?.amount_pab !== undefined && price?.amount_pab !== null && price?.amount_pab !== ''
        ? Number(price.amount_pab)
        : null;
    const item = {
      key: `${p.id}::${v?.id ?? 'default'}`,
      productId: p.id,
      productSlug: p.slug,
      productName: p.name,
      categorySlug: p.category.slug,
      sku: v?.sku || p.sku,
      variantId: v?.id ?? null,
      size: v?.size || 'Única',
      color: v?.color || this.selectedColor() || '',
      unitPricePab: numericPrice !== null && Number.isFinite(numericPrice) ? numericPrice : null,
      currency: price?.currency || 'PAB',
      quantity: this.selectedQuantity(),
      imageUrl: this.activeImage().url,
      imageAlt: this.activeImage().alt,
    };
    return buildWhatsappInquiryUrl([item], this.whatsappNumber);
  });

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
    private readonly catalogApi: CatalogApiService,
    readonly cart: InquiryCartService,
    @Inject(WHATSAPP_NUMBER) private readonly whatsappNumber: string
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
    this.selectedQuantity.set(1);
    this.addedFeedback.set(null);

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
    this.addedFeedback.set(null);
  }

  incrementQuantity(): void {
    this.selectedQuantity.update((q) => Math.min(this.maxQuantity, q + 1));
  }

  decrementQuantity(): void {
    this.selectedQuantity.update((q) => Math.max(1, q - 1));
  }

  addToInquiryCart(): void {
    const p = this.product();
    if (!p || !this.canAddToCart()) {
      return;
    }
    const v = this.selectedVariant();
    const price = this.activePrice();
    const numericPrice =
      price?.amount_pab !== undefined && price?.amount_pab !== null && price?.amount_pab !== ''
        ? Number(price.amount_pab)
        : null;
    const sizeLabel = v?.size || 'Única';

    this.cart.addItem({
      productId: p.id,
      productSlug: p.slug,
      productName: p.name,
      categorySlug: p.category.slug,
      sku: v?.sku || p.sku,
      variantId: v?.id ?? null,
      size: sizeLabel,
      color: v?.color || this.selectedColor() || '',
      unitPricePab: numericPrice !== null && Number.isFinite(numericPrice) ? numericPrice : null,
      currency: price?.currency || 'PAB',
      quantity: this.selectedQuantity(),
      imageUrl: this.activeImage().url,
      imageAlt: this.activeImage().alt,
    });

    this.addedFeedback.set(
      `Agregado: ${p.name} (Talla ${sizeLabel} × ${this.selectedQuantity()})`
    );
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
