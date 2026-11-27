import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import {
  StockBalance,
  StockDirection,
  StockMovement,
  StockMovementType,
} from '../../../core/models/admin.models';
import {
  CategorySummary,
  ImageOut,
  ProductDetail,
  PublicationStatus,
  VariantOut,
} from '../../../core/models/catalog.models';
import { AdminApiService } from '../../../core/services/admin-api.service';
import { AuthService } from '../../../core/services/auth.service';
import { formatPab } from '../../../core/utils/format-pab';
import { resolveCatalogImageUrl } from '../../../core/utils/media-placeholders';
import { ConfirmDialogComponent } from '../components/confirm-dialog.component';

type EditorTab = 'general' | 'pricing' | 'variants' | 'images';

@Component({
  selector: 'app-admin-product-editor-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ConfirmDialogComponent],
  template: `
    <div class="mx-auto max-w-[1240px] space-y-6">
      <!-- Breadcrumb & Header -->
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <a routerLink="/admin/inventario" class="text-xs font-semibold text-terracotta hover:underline">
            ← Volver al inventario
          </a>
          @if (product(); as prod) {
            <h1 class="mt-1 font-editorial text-2xl font-bold text-denim sm:text-3xl">
              {{ prod.name }}
            </h1>
            <p class="mt-0.5 text-xs text-ink-secondary">
              SKU: {{ prod.sku }} · Categoría: {{ prod.category.name }} · Estado:
              <strong class="text-denim">{{ statusLabel(prod.publication_status) }}</strong>
            </p>
          }
        </div>
      </div>

      @if (feedbackMessage(); as msg) {
        <div role="status" class="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          {{ msg }}
        </div>
      }
      @if (errorMessage(); as err) {
        <div role="alert" class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {{ err }}
        </div>
      }

      @if (loading()) {
        <div class="rounded-2xl border border-border bg-surface p-8 text-center text-sm text-ink-secondary">
          Cargando ficha del producto...
        </div>
      } @else {
        @if (product(); as prod) {
        <!-- Section Tabs -->
        <div role="tablist" aria-label="Secciones del producto" class="flex flex-wrap gap-2 border-b border-border pb-3">
          <button
            type="button"
            role="tab"
            [attr.aria-selected]="activeTab() === 'general'"
            (click)="activeTab.set('general')"
            class="rounded-xl px-4 py-2 text-sm font-semibold transition-colors"
            [ngClass]="activeTab() === 'general' ? 'bg-denim text-white' : 'bg-surface text-ink-secondary hover:bg-cream-warm'"
          >
            Datos y Publicación
          </button>
          <button
            type="button"
            role="tab"
            [attr.aria-selected]="activeTab() === 'pricing'"
            (click)="activeTab.set('pricing')"
            class="rounded-xl px-4 py-2 text-sm font-semibold transition-colors"
            [ngClass]="activeTab() === 'pricing' ? 'bg-denim text-white' : 'bg-surface text-ink-secondary hover:bg-cream-warm'"
          >
            Precio (PAB)
          </button>
          <button
            type="button"
            role="tab"
            [attr.aria-selected]="activeTab() === 'variants'"
            (click)="activeTab.set('variants')"
            class="rounded-xl px-4 py-2 text-sm font-semibold transition-colors"
            [ngClass]="activeTab() === 'variants' ? 'bg-denim text-white' : 'bg-surface text-ink-secondary hover:bg-cream-warm'"
          >
            Variantes e Inventario ({{ prod.variants.length }})
          </button>
          <button
            type="button"
            role="tab"
            [attr.aria-selected]="activeTab() === 'images'"
            (click)="activeTab.set('images')"
            class="rounded-xl px-4 py-2 text-sm font-semibold transition-colors"
            [ngClass]="activeTab() === 'images' ? 'bg-denim text-white' : 'bg-surface text-ink-secondary hover:bg-cream-warm'"
          >
            Fotografías ({{ prod.images.length }})
          </button>
        </div>

        <!-- TAB 1: GENERAL & PUBLICATION -->
        @if (activeTab() === 'general') {
          <section class="rounded-2xl border border-border bg-surface p-6">
            <h2 class="font-editorial text-xl font-bold text-denim">Información general y publicación</h2>
            <p class="mt-1 text-xs text-ink-secondary">
              Cualquier edición o cambio de publicación requiere confirmación explícita antes de persistirse.
            </p>

            <form (ngSubmit)="requestProductSaveConfirm()" #prodForm="ngForm" class="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label for="edit-cat" class="mb-1 block text-xs font-medium text-denim">Categoría *</label>
                <select
                  id="edit-cat"
                  name="category_id"
                  required
                  [disabled]="!auth.canWrite()"
                  [(ngModel)]="productForm.category_id"
                  class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm disabled:bg-cream"
                >
                  @for (cat of categories(); track cat.id) {
                    <option [value]="cat.id">{{ cat.name }}</option>
                  }
                </select>
              </div>

              <div>
                <label for="edit-status" class="mb-1 block text-xs font-medium text-denim">Estado de publicación *</label>
                <select
                  id="edit-status"
                  name="publication_status"
                  required
                  [disabled]="!auth.canWrite()"
                  [(ngModel)]="productForm.publication_status"
                  class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm disabled:bg-cream"
                >
                  <option value="draft">Borrador (oculto)</option>
                  <option value="published">Publicado (visible en catálogo)</option>
                  <option value="archived">Archivado</option>
                </select>
              </div>

              <div>
                <label for="edit-sku" class="mb-1 block text-xs font-medium text-denim">SKU *</label>
                <input
                  id="edit-sku"
                  name="sku"
                  required
                  [disabled]="!auth.canWrite()"
                  [(ngModel)]="productForm.sku"
                  class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm disabled:bg-cream"
                />
              </div>

              <div>
                <label for="edit-slug" class="mb-1 block text-xs font-medium text-denim">Slug (URL) *</label>
                <input
                  id="edit-slug"
                  name="slug"
                  required
                  pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
                  [disabled]="!auth.canWrite()"
                  [(ngModel)]="productForm.slug"
                  class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm disabled:bg-cream"
                />
              </div>

              <div class="sm:col-span-2">
                <label for="edit-name" class="mb-1 block text-xs font-medium text-denim">Nombre del producto *</label>
                <input
                  id="edit-name"
                  name="name"
                  required
                  [disabled]="!auth.canWrite()"
                  [(ngModel)]="productForm.name"
                  class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm disabled:bg-cream"
                />
              </div>

              <div class="sm:col-span-2">
                <label for="edit-desc" class="mb-1 block text-xs font-medium text-denim">Descripción</label>
                <textarea
                  id="edit-desc"
                  name="description"
                  rows="3"
                  [disabled]="!auth.canWrite()"
                  [(ngModel)]="productForm.description"
                  class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm disabled:bg-cream"
                ></textarea>
              </div>

              @if (auth.canWrite()) {
                <div class="flex justify-end sm:col-span-2">
                  <button
                    type="submit"
                    [disabled]="prodForm.invalid"
                    class="rounded-xl bg-terracotta px-5 py-2.5 text-sm font-semibold text-white hover:bg-terracotta-hover disabled:opacity-50"
                  >
                    Guardar y confirmar cambios
                  </button>
                </div>
              }
            </form>
          </section>
        }

        <!-- TAB 2: PRICING (PAB) -->
        @if (activeTab() === 'pricing') {
          <section class="rounded-2xl border border-border bg-surface p-6">
            <h2 class="font-editorial text-xl font-bold text-denim">Precio vigente (B/. PAB)</h2>
            <div class="mt-3 rounded-xl border border-border bg-cream p-4 text-sm">
              <p class="text-ink-secondary">
                Precio actual:
                <strong class="text-lg text-denim">
                  {{ prod.current_price ? formatPrice(prod.current_price.amount_pab) : 'Sin precio definido' }}
                </strong>
              </p>
              @if (prod.current_price?.compare_at_pab) {
                <p class="mt-1 text-xs text-ink-muted">
                  Precio comparación: {{ formatPrice(prod.current_price!.compare_at_pab!) }}
                </p>
              }
            </div>

            @if (auth.canWrite()) {
              <form (ngSubmit)="requestPriceConfirm()" #priceFormRef="ngForm" class="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label for="price-amount" class="mb-1 block text-xs font-medium text-denim">
                    Nuevo precio (B/. PAB) *
                  </label>
                  <input
                    id="price-amount"
                    name="amount_pab"
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    [(ngModel)]="priceForm.amount_pab"
                    class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
                  />
                </div>

                <div>
                  <label for="price-compare" class="mb-1 block text-xs font-medium text-denim">
                    Precio comparación (opcional, ≥ precio)
                  </label>
                  <input
                    id="price-compare"
                    name="compare_at_pab"
                    type="number"
                    step="0.01"
                    min="0"
                    [(ngModel)]="priceForm.compare_at_pab"
                    class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
                  />
                </div>

                <div class="flex justify-end sm:col-span-2">
                  <button
                    type="submit"
                    [disabled]="priceFormRef.invalid"
                    class="rounded-xl bg-denim px-5 py-2.5 text-sm font-semibold text-white hover:bg-denim-deep disabled:opacity-50"
                  >
                    Actualizar precio PAB
                  </button>
                </div>
              </form>
            }
          </section>
        }

        <!-- TAB 3: VARIANTS & INVENTORY -->
        @if (activeTab() === 'variants') {
          <div class="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <!-- Left: Variants List & Create -->
            <section class="space-y-4 lg:col-span-7">
              <div class="rounded-2xl border border-border bg-surface p-5">
                <div class="flex items-center justify-between">
                  <h2 class="font-editorial text-lg font-bold text-denim">Variantes (Tallas y Colores)</h2>
                  @if (auth.canWrite()) {
                    <button
                      type="button"
                      (click)="showNewVariant.set(!showNewVariant())"
                      class="rounded-lg bg-denim px-3 py-1.5 text-xs font-semibold text-white hover:bg-denim-deep"
                    >
                      {{ showNewVariant() ? 'Cerrar formulario' : '+ Nueva variante' }}
                    </button>
                  }
                </div>

                @if (showNewVariant() && auth.canWrite()) {
                  <form (ngSubmit)="submitCreateVariant()" #varForm="ngForm" class="mt-4 grid grid-cols-2 gap-3 rounded-xl border border-border bg-cream p-4">
                    <div>
                      <label for="v-sku" class="mb-1 block text-xs font-medium text-denim">SKU *</label>
                      <input id="v-sku" name="sku" required [(ngModel)]="variantForm.sku" placeholder="LCDJ-JN-32-IND" class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label for="v-size" class="mb-1 block text-xs font-medium text-denim">Talla *</label>
                      <input id="v-size" name="size" required [(ngModel)]="variantForm.size" placeholder="32" class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label for="v-color" class="mb-1 block text-xs font-medium text-denim">Color *</label>
                      <input id="v-color" name="color" required [(ngModel)]="variantForm.color" placeholder="Índigo" class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 text-sm" />
                    </div>
                    <div>
                      <label for="v-hex" class="mb-1 block text-xs font-medium text-denim">Color Hex</label>
                      <input id="v-hex" name="color_hex" pattern="^#[0-9A-Fa-f]{6}$" [(ngModel)]="variantForm.color_hex" placeholder="#162D4C" class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 text-sm" />
                    </div>
                    <div class="col-span-2 flex justify-end">
                      <button type="submit" [disabled]="varForm.invalid" class="rounded-lg bg-terracotta px-4 py-1.5 text-xs font-semibold text-white hover:bg-terracotta-hover disabled:opacity-50">
                        Guardar variante
                      </button>
                    </div>
                  </form>
                }

                <div class="mt-4 space-y-2">
                  @for (v of prod.variants; track v.id) {
                    <div
                      (click)="selectVariant(v)"
                      class="flex cursor-pointer flex-wrap items-center justify-between gap-2 rounded-xl border p-3 transition-colors"
                      [ngClass]="
                        selectedVariant()?.id === v.id
                          ? 'border-denim bg-denim-soft/60'
                          : 'border-border bg-white hover:bg-cream/60'
                      "
                    >
                      <div class="flex items-center gap-2.5">
                        @if (v.color_hex) {
                          <span class="h-4 w-4 rounded-full border border-black/15" [style.background]="v.color_hex"></span>
                        }
                        <div>
                          <p class="text-sm font-semibold text-denim">
                            Talla {{ v.size }} · {{ v.color }}
                          </p>
                          <p class="text-xs text-ink-muted">SKU: {{ v.sku }} · {{ statusLabel(v.publication_status) }}</p>
                        </div>
                      </div>
                      <span
                        class="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                        [ngClass]="
                          (v.stock?.available_quantity ?? 0) > 0
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-red-100 text-red-800'
                        "
                      >
                        {{ v.stock?.available_quantity ?? 0 }} disp.
                      </span>
                    </div>
                  }
                </div>
              </div>
            </section>

            <!-- Right: Selected Variant Stock Balance, Atomic Adjustment & History -->
            <section class="space-y-4 lg:col-span-5">
              @if (selectedVariant(); as variant) {
                <div class="rounded-2xl border border-border bg-surface p-5 space-y-4">
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wider text-terracotta">
                      Inventario atómico
                    </p>
                    <h3 class="font-editorial text-lg font-bold text-denim">
                      {{ variant.sku }} (Talla {{ variant.size }} · {{ variant.color }})
                    </h3>
                  </div>

                  @if (variantBalance(); as bal) {
                    <div class="grid grid-cols-3 gap-2 rounded-xl border border-border bg-cream p-3 text-center">
                      <div>
                        <p class="text-[11px] text-ink-muted">Total</p>
                        <p class="text-lg font-bold text-denim">{{ bal.quantity }}</p>
                      </div>
                      <div>
                        <p class="text-[11px] text-ink-muted">Reservado</p>
                        <p class="text-lg font-bold text-amber-700">{{ bal.reserved_quantity }}</p>
                      </div>
                      <div>
                        <p class="text-[11px] text-ink-muted">Disponible</p>
                        <p class="text-lg font-bold text-emerald-700">{{ bal.available_quantity }}</p>
                      </div>
                    </div>
                  }

                  @if (auth.canWrite()) {
                    <form (ngSubmit)="requestStockConfirm()" #stockFormRef="ngForm" class="space-y-3 border-t border-border pt-4">
                      <h4 class="text-xs font-semibold uppercase tracking-wider text-denim">
                        Registrar movimiento de stock
                      </h4>

                      <div class="grid grid-cols-2 gap-2.5">
                        <div>
                          <label for="st-dir" class="mb-1 block text-xs font-medium text-denim">Dirección *</label>
                          <select
                            id="st-dir"
                            name="direction"
                            required
                            [(ngModel)]="stockForm.direction"
                            (ngModelChange)="onDirectionChange($event)"
                            class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 text-xs"
                          >
                            <option value="in">Entrada (in)</option>
                            <option value="out">Salida (out)</option>
                            <option value="adjustment">Ajuste (adjustment)</option>
                          </select>
                        </div>

                        <div>
                          <label for="st-type" class="mb-1 block text-xs font-medium text-denim">Tipo *</label>
                          <select
                            id="st-type"
                            name="movement_type"
                            required
                            [(ngModel)]="stockForm.movement_type"
                            class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 text-xs"
                          >
                            <option value="restock">Reabastecimiento</option>
                            <option value="manual_adjustment">Ajuste manual</option>
                            <option value="sale_consumption">Consumo / Venta</option>
                            <option value="return_in">Devolución</option>
                            <option value="damage_out">Merma / Daño</option>
                          </select>
                        </div>
                      </div>

                      <div class="grid grid-cols-2 gap-2.5">
                        <div>
                          <label for="st-qty" class="mb-1 block text-xs font-medium text-denim">Cantidad *</label>
                          <input
                            id="st-qty"
                            name="quantity"
                            type="number"
                            min="1"
                            required
                            [(ngModel)]="stockForm.quantity"
                            class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 text-sm"
                          />
                        </div>
                        <div>
                          <label for="st-idem" class="mb-1 block text-xs font-medium text-denim">Clave idempotencia</label>
                          <input
                            id="st-idem"
                            name="idempotency_key"
                            [(ngModel)]="stockForm.idempotency_key"
                            class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 font-mono text-xs"
                          />
                        </div>
                      </div>

                      <div>
                        <label for="st-note" class="mb-1 block text-xs font-medium text-denim">Motivo / Nota</label>
                        <input
                          id="st-note"
                          name="note"
                          [(ngModel)]="stockForm.note"
                          placeholder="Ej: Conteo físico semanal"
                          class="w-full rounded-lg border border-border-strong bg-white px-2.5 py-1.5 text-sm"
                        />
                      </div>

                      <button
                        type="submit"
                        [disabled]="stockFormRef.invalid"
                        class="w-full rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white hover:bg-terracotta-hover disabled:opacity-50"
                      >
                        Aplicar movimiento con confirmación
                      </button>
                    </form>
                  }

                  <!-- History -->
                  <div class="border-t border-border pt-4">
                    <h4 class="text-xs font-semibold uppercase tracking-wider text-denim">
                      Historial reciente (append-only)
                    </h4>
                    @if (variantMovements().length === 0) {
                      <p class="mt-2 text-xs text-ink-muted">Sin movimientos registrados.</p>
                    } @else {
                      <ul class="mt-2 max-h-64 space-y-2 overflow-y-auto text-xs">
                        @for (m of variantMovements(); track m.id) {
                          <li class="rounded-lg border border-border bg-white p-2.5">
                            <div class="flex items-center justify-between font-semibold text-denim">
                              <span>{{ m.direction.toUpperCase() }} · {{ m.movement_type }}</span>
                              <span>{{ m.quantity_before }} → {{ m.quantity_after }} ({{ m.quantity }})</span>
                            </div>
                            @if (m.note) {
                              <p class="mt-0.5 text-ink-secondary">{{ m.note }}</p>
                            }
                            <p class="mt-0.5 text-[10px] text-ink-muted">{{ m.created_at | date:'short' }}</p>
                          </li>
                        }
                      </ul>
                    }
                  </div>
                </div>
              } @else {
                <div class="rounded-2xl border border-border bg-surface p-6 text-center text-sm text-ink-secondary">
                  Selecciona una variante para consultar existencias e historial.
                </div>
              }
            </section>
          </div>
        }

        <!-- TAB 4: IMAGES & UPLOAD -->
        @if (activeTab() === 'images') {
          <section class="space-y-5 rounded-2xl border border-border bg-surface p-6">
            <h2 class="font-editorial text-xl font-bold text-denim">Fotografías del producto</h2>

            @if (auth.canWrite()) {
              <form (ngSubmit)="submitImageUpload()" class="grid grid-cols-1 gap-3.5 rounded-xl border border-border bg-cream p-4 sm:grid-cols-2">
                <div class="sm:col-span-2">
                  <label for="img-file" class="mb-1 block text-xs font-medium text-denim">
                    Subir fotografía (JPEG, PNG o WebP · máx. 5 MB)
                  </label>
                  <input
                    id="img-file"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    (change)="onFileSelected($event)"
                    class="w-full rounded-lg border border-border-strong bg-white px-3 py-2 text-xs"
                  />
                </div>
                <div>
                  <label for="img-alt" class="mb-1 block text-xs font-medium text-denim">Texto alternativo (accesibilidad)</label>
                  <input
                    id="img-alt"
                    name="alt_text"
                    [(ngModel)]="uploadAltText"
                    placeholder="Vista frontal del jean"
                    class="w-full rounded-lg border border-border-strong bg-white px-3 py-2 text-sm"
                  />
                </div>
                <div class="flex items-end justify-between gap-3">
                  <label class="inline-flex items-center gap-2 text-xs font-medium text-denim">
                    <input type="checkbox" name="is_primary" [(ngModel)]="uploadIsPrimary" class="h-4 w-4 rounded" />
                    Marcar como principal
                  </label>
                  <button
                    type="submit"
                    [disabled]="!selectedFile() || uploadingImage()"
                    class="rounded-xl bg-terracotta px-4 py-2 text-xs font-semibold text-white hover:bg-terracotta-hover disabled:opacity-50"
                  >
                    {{ uploadingImage() ? 'Subiendo...' : 'Subir fotografía' }}
                  </button>
                </div>
              </form>
            }

            @if (prod.images.length === 0) {
              <p class="text-sm text-ink-secondary">Este producto aún no tiene fotografías registradas.</p>
            } @else {
              <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                @for (img of prod.images; track img.id) {
                  <div class="overflow-hidden rounded-xl border border-border bg-white">
                    <img
                      [src]="resolveImage(img, prod)"
                      [alt]="img.alt_text || prod.name"
                      class="h-48 w-full object-cover"
                    />
                    <div class="space-y-2 p-3 text-xs">
                      <div class="flex items-center justify-between">
                        <span class="truncate font-semibold text-denim">{{ img.original_filename }}</span>
                        @if (img.is_primary) {
                          <span class="rounded-full bg-terracotta px-2 py-0.5 text-[10px] font-bold text-white">
                            Principal
                          </span>
                        }
                      </div>
                      <p class="text-ink-muted">{{ img.width }}×{{ img.height }} · {{ img.mime_type }}</p>
                      @if (auth.canWrite()) {
                        <div class="flex gap-2 pt-1">
                          @if (!img.is_primary) {
                            <button
                              type="button"
                              (click)="setPrimaryImage(img)"
                              class="flex-1 rounded-lg border border-border-strong px-2.5 py-1 font-medium text-denim hover:bg-denim-soft"
                            >
                              Hacer principal
                            </button>
                          }
                          <button
                            type="button"
                            (click)="requestDeleteImage(img)"
                            class="rounded-lg border border-red-200 px-2.5 py-1 font-medium text-red-700 hover:bg-red-50"
                          >
                            Eliminar
                          </button>
                        </div>
                      }
                    </div>
                  </div>
                }
              </div>
            }
          </section>
        }
        }
      }
    </div>

    <app-confirm-dialog
      [open]="confirmOpen()"
      [title]="confirmTitle()"
      [message]="confirmMessage()"
      [details]="confirmDetails()"
      [confirmLabel]="confirmLabel()"
      [tone]="confirmTone()"
      [busy]="confirmBusy()"
      (confirmed)="executeConfirm()"
      (cancelled)="closeConfirm()"
    />
  `,
})
export class AdminProductEditorPageComponent implements OnInit {
  readonly product = signal<ProductDetail | null>(null);
  readonly categories = signal<CategorySummary[]>([]);
  readonly loading = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly feedbackMessage = signal<string | null>(null);
  readonly activeTab = signal<EditorTab>('general');

  // Product general form
  productForm: {
    category_id: string;
    sku: string;
    name: string;
    slug: string;
    description: string;
    publication_status: PublicationStatus;
  } = {
    category_id: '',
    sku: '',
    name: '',
    slug: '',
    description: '',
    publication_status: 'draft',
  };

  // Price form
  priceForm: { amount_pab: string; compare_at_pab: string } = {
    amount_pab: '',
    compare_at_pab: '',
  };

  // Variants & Inventory
  readonly showNewVariant = signal(false);
  variantForm = { sku: '', size: '', color: '', color_hex: '#162D4C' };
  readonly selectedVariant = signal<VariantOut | null>(null);
  readonly variantBalance = signal<StockBalance | null>(null);
  readonly variantMovements = signal<StockMovement[]>([]);

  stockForm: {
    direction: StockDirection;
    movement_type: StockMovementType;
    quantity: number;
    idempotency_key: string;
    note: string;
  } = {
    direction: 'in',
    movement_type: 'restock',
    quantity: 1,
    idempotency_key: this.generateIdempotencyKey(),
    note: '',
  };

  // Image upload
  readonly selectedFile = signal<File | null>(null);
  readonly uploadingImage = signal(false);
  uploadAltText = '';
  uploadIsPrimary = false;

  // Confirm modal
  readonly confirmOpen = signal(false);
  readonly confirmTitle = signal('');
  readonly confirmMessage = signal('');
  readonly confirmDetails = signal<string[]>([]);
  readonly confirmLabel = signal('Confirmar');
  readonly confirmTone = signal<'default' | 'danger'>('default');
  readonly confirmBusy = signal(false);
  private pendingAction: (() => void) | null = null;

  private productId = '';

  constructor(
    readonly auth: AuthService,
    private readonly adminApi: AdminApiService,
    private readonly route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.productId = this.route.snapshot.paramMap.get('id') ?? '';
    this.adminApi.listCategories({ page: 1, page_size: 100 }).subscribe({
      next: (res) => this.categories.set(res.items),
    });
    if (this.productId) {
      this.loadProduct();
    }
  }

  loadProduct(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.adminApi.getProduct(this.productId).subscribe({
      next: (prod) => {
        this.product.set(prod);
        this.productForm = {
          category_id: prod.category_id,
          sku: prod.sku,
          name: prod.name,
          slug: prod.slug,
          description: prod.description ?? '',
          publication_status: prod.publication_status,
        };
        this.priceForm = {
          amount_pab: prod.current_price?.amount_pab ?? '',
          compare_at_pab: prod.current_price?.compare_at_pab ?? '',
        };
        this.loading.set(false);
        const currentSelected = this.selectedVariant();
        const match = currentSelected
          ? prod.variants.find((v) => v.id === currentSelected.id) ?? prod.variants[0] ?? null
          : prod.variants[0] ?? null;
        if (match) {
          this.selectVariant(match);
        }
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.errorMessage.set(this.adminApi.extractErrorMessage(err));
      },
    });
  }

  requestProductSaveConfirm(): void {
    this.confirmTitle.set('Confirmar edición y publicación');
    this.confirmMessage.set('¿Deseas guardar los cambios realizados en este producto?');
    this.confirmDetails.set([
      `Nombre: ${this.productForm.name}`,
      `SKU: ${this.productForm.sku}`,
      `Estado: ${this.statusLabel(this.productForm.publication_status)}`,
    ]);
    this.confirmLabel.set('Guardar cambios');
    this.confirmTone.set('default');
    this.pendingAction = () => {
      this.confirmBusy.set(true);
      this.adminApi
        .updateProduct(this.productId, {
          category_id: this.productForm.category_id,
          sku: this.productForm.sku.trim(),
          name: this.productForm.name.trim(),
          slug: this.productForm.slug.trim(),
          description: this.productForm.description.trim() || null,
          publication_status: this.productForm.publication_status,
        })
        .subscribe({
          next: (updated) => {
            this.product.set(updated);
            this.confirmBusy.set(false);
            this.closeConfirm();
            this.feedbackMessage.set('Producto actualizado correctamente.');
          },
          error: (err: unknown) => {
            this.confirmBusy.set(false);
            this.closeConfirm();
            this.errorMessage.set(this.adminApi.extractErrorMessage(err));
          },
        });
    };
    this.confirmOpen.set(true);
  }

  requestPriceConfirm(): void {
    const amount = Number(this.priceForm.amount_pab);
    const compare = this.priceForm.compare_at_pab ? Number(this.priceForm.compare_at_pab) : null;
    if (compare !== null && compare < amount) {
      this.errorMessage.set('El precio de comparación debe ser mayor o igual al precio vigente.');
      return;
    }

    this.confirmTitle.set('Confirmar cambio de precio (PAB)');
    this.confirmMessage.set('El nuevo precio quedará vigente inmediatamente en el catálogo.');
    this.confirmDetails.set([
      `Precio vigente: ${formatPab(amount)}`,
      ...(compare !== null ? [`Precio comparación: ${formatPab(compare)}`] : []),
    ]);
    this.confirmLabel.set('Actualizar precio');
    this.confirmTone.set('default');
    this.pendingAction = () => {
      this.confirmBusy.set(true);
      this.adminApi
        .setCurrentPrice(this.productId, {
          amount_pab: amount.toFixed(2),
          compare_at_pab: compare !== null ? compare.toFixed(2) : null,
          currency: 'PAB',
        })
        .subscribe({
          next: () => {
            this.confirmBusy.set(false);
            this.closeConfirm();
            this.feedbackMessage.set('Precio PAB actualizado correctamente.');
            this.loadProduct();
          },
          error: (err: unknown) => {
            this.confirmBusy.set(false);
            this.closeConfirm();
            this.errorMessage.set(this.adminApi.extractErrorMessage(err));
          },
        });
    };
    this.confirmOpen.set(true);
  }

  submitCreateVariant(): void {
    this.errorMessage.set(null);
    this.adminApi
      .createVariant(this.productId, {
        sku: this.variantForm.sku.trim(),
        size: this.variantForm.size.trim(),
        color: this.variantForm.color.trim(),
        color_hex: this.variantForm.color_hex.trim() || null,
        publication_status: 'published',
      })
      .subscribe({
        next: () => {
          this.showNewVariant.set(false);
          this.variantForm = { sku: '', size: '', color: '', color_hex: '#162D4C' };
          this.feedbackMessage.set('Variante creada correctamente.');
          this.loadProduct();
        },
        error: (err: unknown) => {
          this.errorMessage.set(this.adminApi.extractErrorMessage(err));
        },
      });
  }

  selectVariant(variant: VariantOut): void {
    this.selectedVariant.set(variant);
    this.stockForm.idempotency_key = this.generateIdempotencyKey();
    this.adminApi.getVariantBalance(variant.id).subscribe({
      next: (bal) => this.variantBalance.set(bal),
      error: () => this.variantBalance.set(null),
    });
    this.adminApi.listVariantMovements(variant.id, 1, 20).subscribe({
      next: (res) => this.variantMovements.set(res.items),
      error: () => this.variantMovements.set([]),
    });
  }

  onDirectionChange(direction: StockDirection): void {
    if (direction === 'in') this.stockForm.movement_type = 'restock';
    else if (direction === 'out') this.stockForm.movement_type = 'sale_consumption';
    else this.stockForm.movement_type = 'manual_adjustment';
  }

  requestStockConfirm(): void {
    const variant = this.selectedVariant();
    if (!variant) return;

    this.confirmTitle.set('Confirmar movimiento atómico de inventario');
    this.confirmMessage.set('Esta operación quedará registrada de forma inmutable en el historial.');
    this.confirmDetails.set([
      `Variante: ${variant.sku} (Talla ${variant.size} · ${variant.color})`,
      `Movimiento: ${this.stockForm.direction.toUpperCase()} · ${this.stockForm.movement_type}`,
      `Cantidad: ${this.stockForm.quantity}`,
      `Idempotency Key: ${this.stockForm.idempotency_key || 'Automática'}`,
    ]);
    this.confirmLabel.set('Aplicar movimiento');
    this.confirmTone.set('default');
    this.pendingAction = () => {
      this.confirmBusy.set(true);
      this.adminApi
        .createStockMovement({
          variant_id: variant.id,
          direction: this.stockForm.direction,
          movement_type: this.stockForm.movement_type,
          quantity: Number(this.stockForm.quantity),
          idempotency_key: this.stockForm.idempotency_key.trim() || null,
          note: this.stockForm.note.trim() || null,
        })
        .subscribe({
          next: (res) => {
            this.confirmBusy.set(false);
            this.closeConfirm();
            this.stockForm.note = '';
            this.stockForm.idempotency_key = this.generateIdempotencyKey();
            this.feedbackMessage.set(
              res.idempotent_replay
                ? `Movimiento idempotente ya aplicado (${res.quantity_after} uds).`
                : `Stock actualizado: ${res.quantity_before} → ${res.quantity_after} uds.`
            );
            this.loadProduct();
          },
          error: (err: unknown) => {
            this.confirmBusy.set(false);
            this.closeConfirm();
            this.errorMessage.set(this.adminApi.extractErrorMessage(err));
          },
        });
    };
    this.confirmOpen.set(true);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    if (!file) {
      this.selectedFile.set(null);
      return;
    }
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      this.errorMessage.set('Solo se permiten imágenes JPEG, PNG o WebP.');
      this.selectedFile.set(null);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.errorMessage.set('La imagen supera el límite de 5 MB.');
      this.selectedFile.set(null);
      return;
    }
    this.errorMessage.set(null);
    this.selectedFile.set(file);
  }

  submitImageUpload(): void {
    const file = this.selectedFile();
    if (!file) return;

    this.uploadingImage.set(true);
    this.errorMessage.set(null);
    this.adminApi
      .uploadProductImage(this.productId, file, {
        alt_text: this.uploadAltText || null,
        is_primary: this.uploadIsPrimary,
      })
      .subscribe({
        next: () => {
          this.uploadingImage.set(false);
          this.selectedFile.set(null);
          this.uploadAltText = '';
          this.uploadIsPrimary = false;
          this.feedbackMessage.set('Fotografía cargada correctamente.');
          this.loadProduct();
        },
        error: (err: unknown) => {
          this.uploadingImage.set(false);
          this.errorMessage.set(this.adminApi.extractErrorMessage(err));
        },
      });
  }

  setPrimaryImage(img: ImageOut): void {
    this.adminApi.updateImageMetadata(img.id, { is_primary: true }).subscribe({
      next: () => {
        this.feedbackMessage.set('Imagen principal actualizada.');
        this.loadProduct();
      },
      error: (err: unknown) => this.errorMessage.set(this.adminApi.extractErrorMessage(err)),
    });
  }

  requestDeleteImage(img: ImageOut): void {
    this.confirmTitle.set('Eliminar fotografía');
    this.confirmMessage.set(`¿Deseas eliminar "${img.original_filename}" de este producto?`);
    this.confirmDetails.set([`Archivo: ${img.original_filename}`]);
    this.confirmLabel.set('Eliminar');
    this.confirmTone.set('danger');
    this.pendingAction = () => {
      this.confirmBusy.set(true);
      this.adminApi.deleteImageMetadata(img.id).subscribe({
        next: () => {
          this.confirmBusy.set(false);
          this.closeConfirm();
          this.feedbackMessage.set('Fotografía eliminada.');
          this.loadProduct();
        },
        error: (err: unknown) => {
          this.confirmBusy.set(false);
          this.closeConfirm();
          this.errorMessage.set(this.adminApi.extractErrorMessage(err));
        },
      });
    };
    this.confirmOpen.set(true);
  }

  executeConfirm(): void {
    this.pendingAction?.();
  }

  closeConfirm(): void {
    this.confirmOpen.set(false);
    this.pendingAction = null;
  }

  formatPrice(amount: string): string {
    return formatPab(amount);
  }

  resolveImage(img: ImageOut, prod: ProductDetail): string {
    return resolveCatalogImageUrl(img.storage_path, prod.slug || prod.category.slug);
  }

  statusLabel(status: PublicationStatus): string {
    switch (status) {
      case 'published':
        return 'Publicado';
      case 'draft':
        return 'Borrador';
      case 'archived':
        return 'Archivado';
    }
  }

  private generateIdempotencyKey(): string {
    return `adm-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  }
}
