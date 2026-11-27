import { CommonModule } from '@angular/common';
import { Component, Inject, computed } from '@angular/core';
import { RouterLink } from '@angular/router';
import { WHATSAPP_NUMBER } from '../../core/config/api-config';
import { InquiryCartItem, INQUIRY_CART_MAX_QUANTITY } from '../../core/models/inquiry-cart.models';
import { InquiryCartService } from '../../core/services/inquiry-cart.service';
import { formatPab } from '../../core/utils/format-pab';
import { getPlaceholderPhoto } from '../../core/utils/media-placeholders';
import {
  buildWhatsappInquiryMessage,
  buildWhatsappInquiryUrl,
  formatWhatsappDisplayNumber,
} from '../../core/utils/whatsapp-link';

@Component({
  selector: 'app-inquiry-cart-page',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="mx-auto max-w-[1240px] px-4 py-8 md:px-7 md:py-10">
      <!-- Page Header -->
      <div class="mb-6 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
            Consulta sin compromiso
          </p>
          <h1 class="mt-1 font-editorial text-3xl font-bold text-denim sm:text-4xl">
            Tu lista de consulta
          </h1>
        </div>

        <div class="flex flex-wrap items-center gap-2.5">
          @if (!cart.isEmpty()) {
            <button
              type="button"
              (click)="cart.clear()"
              class="rounded-xl border border-border-strong bg-white px-4 py-2 text-xs font-semibold text-ink-secondary transition-colors hover:border-[#991b1b]/40 hover:bg-[#fee2e2]/40 hover:text-[#991b1b]"
            >
              Vaciar lista
            </button>
          }
          <a
            routerLink="/catalogo"
            class="rounded-xl border border-denim/25 bg-surface px-4 py-2 text-xs font-semibold text-denim transition-colors hover:bg-denim-soft"
          >
            Seguir explorando
          </a>
        </div>
      </div>

      @if (cart.isEmpty()) {
        <!-- Empty State -->
        <section
          aria-label="Lista de consulta vacía"
          class="mx-auto max-w-xl rounded-2xl border border-border bg-surface px-6 py-12 text-center shadow-sm"
        >
          <div
            class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-denim-soft text-denim"
            aria-hidden="true"
          >
            <svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15.75 10.5V6a3.75 3.75 0 1 0-7.5 0v4.5m11.356-1.993 1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 0 1-1.12-1.243l1.264-12A1.125 1.125 0 0 1 5.513 7.5h12.974c.576 0 1.059.435 1.119 1.007Z"
              />
            </svg>
          </div>
          <h2 class="mt-4 font-editorial text-2xl font-bold text-denim">
            Aún no has agregado prendas
          </h2>
          <p class="mt-2 text-sm leading-relaxed text-ink-secondary">
            Explora el catálogo, selecciona tu talla y cantidad, y prepara tu consulta para enviarla
            directamente por WhatsApp sin crear cuenta ni realizar pagos en línea.
          </p>
          <div class="mt-6 flex flex-wrap items-center justify-center gap-3">
            <a
              routerLink="/catalogo"
              class="inline-flex items-center justify-center rounded-xl bg-denim px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-denim-deep"
            >
              Explorar catálogo
            </a>
          </div>
        </section>
      } @else {
        <!-- Cart Layout: Items + Indicative Summary -->
        <div class="grid gap-8 lg:grid-cols-12">
          <!-- Items List -->
          <section aria-label="Prendas en tu lista de consulta" class="space-y-4 lg:col-span-7">
            @for (item of cart.items(); track item.key) {
              <article
                class="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-4 shadow-sm sm:flex-row sm:items-center"
              >
                <a
                  [routerLink]="['/producto', item.productSlug]"
                  class="block h-28 w-24 shrink-0 overflow-hidden rounded-xl border border-border bg-cream-warm"
                >
                  <img
                    [src]="item.imageUrl || fallbackImage(item)"
                    [alt]="item.imageAlt"
                    (error)="onImageError($event, item)"
                    class="h-full w-full object-cover"
                  />
                </a>

                <div class="min-w-0 flex-1">
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <a
                        [routerLink]="['/producto', item.productSlug]"
                        class="font-editorial text-lg font-bold leading-snug text-denim hover:text-terracotta hover:underline"
                      >
                        {{ item.productName }}
                      </a>
                      <p class="mt-0.5 text-xs text-ink-muted">
                        SKU: <span class="font-medium text-ink">{{ item.sku }}</span>
                      </p>
                    </div>

                    <button
                      type="button"
                      (click)="cart.removeItem(item.key)"
                      [attr.aria-label]="'Quitar ' + item.productName + ' talla ' + item.size"
                      class="rounded-lg p-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-[#fee2e2]/60 hover:text-[#991b1b]"
                    >
                      Quitar
                    </button>
                  </div>

                  <div class="mt-2.5 flex flex-wrap items-center gap-2 text-xs">
                    <span class="rounded-full border border-border bg-white px-2.5 py-0.5 font-medium text-denim">
                      Talla: {{ item.size }}
                    </span>
                    @if (item.color) {
                      <span class="rounded-full border border-border bg-white px-2.5 py-0.5 text-ink-secondary">
                        Color: {{ item.color }}
                      </span>
                    }
                    <span class="text-ink-secondary">
                      Unitario: <strong class="text-ink">{{ formatUnitPrice(item) }}</strong>
                    </span>
                  </div>

                  <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <!-- Quantity Stepper -->
                    <div class="inline-flex items-center rounded-xl border border-border-strong bg-white">
                      <button
                        type="button"
                        (click)="cart.decrement(item.key)"
                        [attr.aria-label]="'Disminuir cantidad de ' + item.productName"
                        class="flex h-9 w-9 items-center justify-center text-base font-semibold text-denim transition-colors hover:bg-cream-warm"
                      >
                        −
                      </button>
                      <span
                        class="min-w-[2.25rem] text-center text-sm font-semibold text-ink"
                        [attr.aria-label]="'Cantidad: ' + item.quantity"
                      >
                        {{ item.quantity }}
                      </span>
                      <button
                        type="button"
                        (click)="cart.increment(item.key)"
                        [disabled]="item.quantity >= maxQuantity"
                        [attr.aria-label]="'Aumentar cantidad de ' + item.productName"
                        class="flex h-9 w-9 items-center justify-center text-base font-semibold text-denim transition-colors hover:bg-cream-warm disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        +
                      </button>
                    </div>

                    <div class="text-right">
                      <p class="text-[11px] uppercase tracking-wide text-ink-muted">Subtotal indicativo</p>
                      <p class="text-base font-bold text-denim">{{ formatLineSubtotal(item) }}</p>
                    </div>
                  </div>
                </div>
              </article>
            }
          </section>

          <!-- Summary & WhatsApp Preview -->
          <aside aria-label="Resumen de consulta" class="lg:col-span-5">
            <div class="sticky top-24 rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <h2 class="font-editorial text-2xl font-bold text-denim">Resumen indicativo</h2>

              <dl class="mt-4 space-y-2.5 border-b border-border pb-4 text-sm">
                <div class="flex items-center justify-between">
                  <dt class="text-ink-secondary">Prendas seleccionadas</dt>
                  <dd class="font-semibold text-ink">{{ cart.totalUnits() }}</dd>
                </div>
                <div class="flex items-center justify-between text-base">
                  <dt class="font-medium text-denim">Total referencial</dt>
                  <dd class="text-xl font-bold text-terracotta">{{ totalFormatted() }}</dd>
                </div>
              </dl>

              @if (cart.hasUnpricedItems()) {
                <p class="mt-3 text-xs text-ink-secondary">
                  Algunas prendas tienen precio por confirmar; el total mostrado es parcial.
                </p>
              }

              <div class="mt-4 rounded-xl border border-border bg-cream/80 p-3.5 text-xs leading-relaxed text-ink-secondary">
                <p class="font-semibold text-denim">
                  Atención por WhatsApp · {{ whatsappDisplayNumber }}
                </p>
                <p class="mt-1">
                  Esta lista se guarda localmente en tu navegador. Enviar la consulta no genera orden,
                  no realiza cobros en línea ni reserva inventario.
                </p>
              </div>

              <div class="mt-5">
                <label for="wa-preview" class="block text-xs font-semibold uppercase tracking-[0.12em] text-ink-secondary">
                  Vista previa del mensaje
                </label>
                <pre
                  id="wa-preview"
                  aria-live="polite"
                  class="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap rounded-xl border border-border bg-white p-3.5 font-sans text-xs leading-relaxed text-ink"
                >{{ whatsappMessage() }}</pre>
              </div>

              <a
                [href]="whatsappUrl()"
                target="_blank"
                rel="noopener noreferrer"
                class="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#1f8b4c] px-5 py-3.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#16773f]"
              >
                <svg class="h-5 w-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path
                    d="M20.52 3.48A11.86 11.86 0 0 0 12.06 0C5.49 0 .14 5.35.14 11.92c0 2.1.55 4.15 1.6 5.96L0 24l6.29-1.65a11.9 11.9 0 0 0 5.77 1.47h.01c6.57 0 11.92-5.35 11.92-11.92 0-3.18-1.24-6.17-3.47-8.42Zm-8.46 18.33h-.01a9.89 9.89 0 0 1-5.04-1.38l-.36-.21-3.73.98 1-3.64-.24-.37a9.88 9.88 0 0 1-1.52-5.27c0-5.46 4.44-9.9 9.91-9.9 2.65 0 5.13 1.03 7 2.9a9.84 9.84 0 0 1 2.9 7c0 5.46-4.45 9.89-9.91 9.89Zm5.43-7.42c-.3-.15-1.76-.87-2.04-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.17-.17.2-.35.22-.65.07-.3-.15-1.26-.46-2.4-1.48-.89-.79-1.49-1.77-1.66-2.07-.17-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.07-.15-.67-1.62-.92-2.22-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.02-1.04 2.48s1.07 2.88 1.22 3.08c.15.2 2.1 3.21 5.09 4.5.71.31 1.27.49 1.7.63.71.23 1.36.2 1.87.12.57-.09 1.76-.72 2.01-1.42.25-.7.25-1.3.17-1.42-.07-.12-.27-.2-.57-.35Z"
                  />
                </svg>
                Enviar consulta por WhatsApp
              </a>
            </div>
          </aside>
        </div>
      }
    </div>
  `,
})
export class InquiryCartPageComponent {
  readonly maxQuantity = INQUIRY_CART_MAX_QUANTITY;
  readonly whatsappDisplayNumber: string;

  readonly totalFormatted = computed(() => formatPab(this.cart.subtotalPab(), 'PAB'));
  readonly whatsappMessage = computed(() => buildWhatsappInquiryMessage(this.cart.items()));
  readonly whatsappUrl = computed(() =>
    buildWhatsappInquiryUrl(this.cart.items(), this.whatsappNumber)
  );

  constructor(
    readonly cart: InquiryCartService,
    @Inject(WHATSAPP_NUMBER) private readonly whatsappNumber: string
  ) {
    this.whatsappDisplayNumber = formatWhatsappDisplayNumber(whatsappNumber);
  }

  formatUnitPrice(item: InquiryCartItem): string {
    return formatPab(item.unitPricePab, item.currency);
  }

  formatLineSubtotal(item: InquiryCartItem): string {
    if (item.unitPricePab === null || !Number.isFinite(item.unitPricePab)) {
      return 'Por confirmar';
    }
    return formatPab(item.unitPricePab * item.quantity, item.currency);
  }

  fallbackImage(item: InquiryCartItem): string {
    return getPlaceholderPhoto(`${item.categorySlug}-${item.productSlug}`).url;
  }

  onImageError(event: Event, item: InquiryCartItem): void {
    const img = event.target as HTMLImageElement | null;
    if (!img || img.dataset['fallbackApplied']) {
      return;
    }
    img.dataset['fallbackApplied'] = 'true';
    img.src = this.fallbackImage(item);
  }
}
