import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ProductListItem } from '../../../core/models/catalog.models';
import { formatPab, getDiscountPercent } from '../../../core/utils/format-pab';
import { getPlaceholderPhoto, resolveCatalogImageUrl } from '../../../core/utils/media-placeholders';

@Component({
  selector: 'app-product-card',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <article
      class="group flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-[0_2px_8px_rgba(22,45,76,0.05)] transition-all duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-[0_10px_28px_rgba(22,45,76,0.09)]"
    >
      <a
        [routerLink]="['/producto', product.slug]"
        class="relative block aspect-[4/5] overflow-hidden bg-cream-warm"
        [attr.aria-label]="'Ver detalle de ' + product.name"
      >
        <img
          [src]="imageUrl"
          [alt]="product.primary_image?.alt_text || product.name"
          (error)="onImageError($event)"
          loading="lazy"
          class="h-full w-full object-cover object-center transition-transform duration-500 group-hover:scale-105"
        />

        <!-- Top Badges -->
        <div class="absolute left-2.5 top-2.5 flex flex-wrap gap-1.5">
          @if (discountPercent) {
            <span class="rounded-full bg-terracotta px-2.5 py-0.5 text-[11px] font-semibold text-white shadow-sm">
              -{{ discountPercent }}%
            </span>
          }
          <span
            class="rounded-full px-2.5 py-0.5 text-[11px] font-semibold shadow-sm"
            [ngClass]="stockBadgeClass"
          >
            {{ stockLabel }}
          </span>
        </div>
      </a>

      <div class="flex flex-1 flex-col p-3.5 sm:p-4">
        <p class="text-[11px] font-semibold uppercase tracking-[0.12em] text-terracotta">
          {{ product.category_name }}
        </p>

        <h3 class="mt-1 font-editorial text-base font-bold leading-snug text-denim sm:text-lg">
          <a
            [routerLink]="['/producto', product.slug]"
            class="hover:text-terracotta focus-visible:rounded-sm"
          >
            {{ product.name }}
          </a>
        </h3>

        <p class="mt-1 text-xs text-ink-muted">SKU: {{ product.sku }}</p>

        <div class="mt-auto pt-3">
          <div class="flex flex-wrap items-baseline gap-2">
            <span class="text-base font-bold text-denim sm:text-lg">
              {{ formattedPrice }}
            </span>
            @if (formattedCompareAt) {
              <span class="text-xs text-ink-muted line-through">
                {{ formattedCompareAt }}
              </span>
            }
          </div>

          <div class="mt-2 flex items-center justify-between text-xs text-ink-secondary">
            <span>
              {{ product.published_variant_count }}
              {{ product.published_variant_count === 1 ? 'variante' : 'variantes' }}
            </span>
            <a
              [routerLink]="['/producto', product.slug]"
              class="font-semibold text-denim group-hover:text-terracotta"
            >
              Ver detalle →
            </a>
          </div>
        </div>
      </div>
    </article>
  `,
})
export class ProductCardComponent {
  @Input({ required: true }) product!: ProductListItem;

  get imageUrl(): string {
    return resolveCatalogImageUrl(
      this.product.primary_image?.storage_path,
      `${this.product.category_slug}-${this.product.slug}`
    );
  }

  get formattedPrice(): string {
    return formatPab(
      this.product.current_price?.amount_pab,
      this.product.current_price?.currency
    );
  }

  get formattedCompareAt(): string | null {
    const compareAt = this.product.current_price?.compare_at_pab;
    if (!compareAt) {
      return null;
    }
    return formatPab(compareAt, this.product.current_price?.currency);
  }

  get discountPercent(): number | null {
    return getDiscountPercent(
      this.product.current_price?.amount_pab,
      this.product.current_price?.compare_at_pab
    );
  }

  get stockLabel(): string {
    if (!this.product.in_stock || this.product.available_stock <= 0) {
      return 'Agotado';
    }
    if (this.product.available_stock <= 3) {
      return 'Pocas unidades';
    }
    return 'Disponible';
  }

  get stockBadgeClass(): string {
    if (!this.product.in_stock || this.product.available_stock <= 0) {
      return 'bg-[#fee2e2] text-[#991b1b]';
    }
    if (this.product.available_stock <= 3) {
      return 'bg-[#ffedd5] text-[#9a3412]';
    }
    return 'bg-[#dcfce7] text-[#166534]';
  }

  onImageError(event: Event): void {
    const img = event.target as HTMLImageElement | null;
    if (!img || img.dataset['fallbackApplied']) {
      return;
    }
    img.dataset['fallbackApplied'] = 'true';
    img.src = getPlaceholderPhoto(this.product.category_slug || this.product.slug).url;
  }
}
