import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { CategorySummary, ProductListItem, PublicationStatus } from '../../../core/models/catalog.models';
import { AdminApiService } from '../../../core/services/admin-api.service';
import { AuthService } from '../../../core/services/auth.service';
import { formatPab } from '../../../core/utils/format-pab';
import { getPlaceholderPhoto, resolveCatalogImageUrl } from '../../../core/utils/media-placeholders';
import { ConfirmDialogComponent } from '../components/confirm-dialog.component';

@Component({
  selector: 'app-admin-inventory-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ConfirmDialogComponent],
  template: `
    <div class="mx-auto max-w-[1280px] space-y-6">
      <!-- Page Header -->
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
            Catálogo e Inventario
          </p>
          <h1 class="mt-1 font-editorial text-2xl font-bold text-denim sm:text-3xl">
            Gestión de productos y existencias
          </h1>
        </div>

        @if (auth.canWrite()) {
          <button
            type="button"
            (click)="openCreateModal()"
            class="rounded-xl bg-terracotta px-4 py-2.5 text-sm font-semibold text-white shadow-xs transition-colors hover:bg-terracotta-hover"
          >
            + Nuevo producto
          </button>
        }
      </div>

      <!-- KPI Cards -->
      <section aria-label="Indicadores de catálogo" class="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        <div class="rounded-2xl border border-border bg-surface p-4">
          <p class="text-xs font-medium text-ink-secondary">Total catálogo</p>
          <p class="mt-1 font-editorial text-2xl font-bold text-denim">{{ totalProducts() }}</p>
        </div>
        <div class="rounded-2xl border border-border bg-surface p-4">
          <p class="text-xs font-medium text-ink-secondary">Publicados (página)</p>
          <p class="mt-1 font-editorial text-2xl font-bold text-emerald-700">{{ publishedCount() }}</p>
        </div>
        <div class="rounded-2xl border border-border bg-surface p-4">
          <p class="text-xs font-medium text-ink-secondary">Borrador / Archivado</p>
          <p class="mt-1 font-editorial text-2xl font-bold text-amber-700">{{ nonPublishedCount() }}</p>
        </div>
        <div class="rounded-2xl border border-border bg-surface p-4">
          <p class="text-xs font-medium text-ink-secondary">Unidades disponibles</p>
          <p class="mt-1 font-editorial text-2xl font-bold text-denim">{{ totalStockOnPage() }}</p>
        </div>
      </section>

      <!-- Filters -->
      <section class="rounded-2xl border border-border bg-surface p-4">
        <form (ngSubmit)="applyFilters()" class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label for="inv-search" class="mb-1 block text-xs font-medium text-ink-secondary">
              Buscar por nombre, SKU o slug
            </label>
            <input
              id="inv-search"
              name="search"
              type="search"
              [(ngModel)]="search"
              placeholder="Ej: Jean, LCDJ-..."
              class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm text-ink"
            />
          </div>

          <div>
            <label for="inv-category" class="mb-1 block text-xs font-medium text-ink-secondary">
              Categoría
            </label>
            <select
              id="inv-category"
              name="categoryId"
              [(ngModel)]="selectedCategoryId"
              (change)="applyFilters()"
              class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm text-ink"
            >
              <option value="">Todas las categorías</option>
              @for (cat of categories(); track cat.id) {
                <option [value]="cat.id">{{ cat.name }}</option>
              }
            </select>
          </div>

          <div>
            <label for="inv-status" class="mb-1 block text-xs font-medium text-ink-secondary">
              Estado de publicación
            </label>
            <select
              id="inv-status"
              name="status"
              [(ngModel)]="selectedStatus"
              (change)="applyFilters()"
              class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm text-ink"
            >
              <option value="">Todos los estados</option>
              <option value="published">Publicado</option>
              <option value="draft">Borrador</option>
              <option value="archived">Archivado</option>
            </select>
          </div>

          <div class="flex items-end gap-2">
            <button
              type="submit"
              class="flex-1 rounded-xl bg-denim px-4 py-2 text-sm font-semibold text-white hover:bg-denim-deep"
            >
              Filtrar
            </button>
            <button
              type="button"
              (click)="resetFilters()"
              class="rounded-xl border border-border-strong bg-white px-3 py-2 text-sm text-ink-secondary hover:bg-cream-warm"
            >
              Limpiar
            </button>
          </div>
        </form>
      </section>

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

      <!-- Products Table -->
      <section class="overflow-hidden rounded-2xl border border-border bg-surface">
        @if (loading()) {
          <div class="p-8 text-center text-sm text-ink-secondary">Cargando productos desde la API...</div>
        } @else if (products().length === 0) {
          <div class="p-8 text-center text-sm text-ink-secondary">
            No se encontraron productos con los filtros seleccionados.
          </div>
        } @else {
          <div class="overflow-x-auto">
            <table class="w-full min-w-[780px] border-collapse text-left text-sm">
              <thead class="border-b border-border bg-cream-warm/70 text-xs font-semibold uppercase tracking-wider text-ink-secondary">
                <tr>
                  <th class="px-4 py-3">Producto</th>
                  <th class="px-4 py-3">Categoría</th>
                  <th class="px-4 py-3">Precio (PAB)</th>
                  <th class="px-4 py-3">Stock</th>
                  <th class="px-4 py-3">Estado</th>
                  <th class="px-4 py-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                @for (item of products(); track item.id) {
                  <tr class="hover:bg-cream/60">
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-3">
                        <img
                          [src]="imageUrl(item)"
                          [alt]="item.name"
                          (error)="onImageError($event, item)"
                          class="h-12 w-10 rounded-lg border border-border object-cover"
                        />
                        <div class="min-w-0">
                          <p class="truncate font-semibold text-denim">{{ item.name }}</p>
                          <p class="text-xs text-ink-muted">SKU: {{ item.sku }} · {{ item.slug }}</p>
                        </div>
                      </div>
                    </td>
                    <td class="px-4 py-3 text-ink-secondary">{{ item.category_name }}</td>
                    <td class="px-4 py-3 font-semibold text-denim">
                      {{ item.current_price ? formatPrice(item.current_price.amount_pab) : 'Sin precio' }}
                    </td>
                    <td class="px-4 py-3">
                      <span
                        class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold"
                        [ngClass]="
                          item.available_stock > 0
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-red-100 text-red-800'
                        "
                      >
                        {{ item.available_stock }} uds
                      </span>
                    </td>
                    <td class="px-4 py-3">
                      <span
                        class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold"
                        [ngClass]="{
                          'bg-emerald-100 text-emerald-800': item.publication_status === 'published',
                          'bg-amber-100 text-amber-800': item.publication_status === 'draft',
                          'bg-slate-200 text-slate-700': item.publication_status === 'archived'
                        }"
                      >
                        {{ statusLabel(item.publication_status) }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-right">
                      <div class="inline-flex items-center gap-2">
                        <a
                          [routerLink]="['/admin/productos', item.id]"
                          class="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-xs font-semibold text-denim hover:bg-denim-soft"
                        >
                          {{ auth.canWrite() ? 'Gestionar' : 'Ver detalle' }}
                        </a>
                        @if (auth.canWrite()) {
                          <button
                            type="button"
                            (click)="requestQuickPublishToggle(item)"
                            class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white"
                            [ngClass]="
                              item.publication_status === 'published'
                                ? 'bg-slate-600 hover:bg-slate-700'
                                : 'bg-terracotta hover:bg-terracotta-hover'
                            "
                          >
                            {{ item.publication_status === 'published' ? 'Pasar a borrador' : 'Publicar' }}
                          </button>
                        }
                      </div>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>

          <!-- Pagination -->
          @if (totalPages() > 1) {
            <div class="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-ink-secondary">
              <span>Página {{ page() }} de {{ totalPages() }} ({{ totalProducts() }} productos)</span>
              <div class="flex gap-2">
                <button
                  type="button"
                  [disabled]="page() <= 1"
                  (click)="goToPage(page() - 1)"
                  class="rounded-lg border border-border-strong bg-white px-3 py-1.5 font-medium disabled:opacity-40"
                >
                  Anterior
                </button>
                <button
                  type="button"
                  [disabled]="page() >= totalPages()"
                  (click)="goToPage(page() + 1)"
                  class="rounded-lg border border-border-strong bg-white px-3 py-1.5 font-medium disabled:opacity-40"
                >
                  Siguiente
                </button>
              </div>
            </div>
          }
        }
      </section>
    </div>

    <!-- Create Product Modal -->
    @if (createModalOpen()) {
      <div
        class="fixed inset-0 z-40 flex items-center justify-center bg-denim-deep/60 p-4 backdrop-blur-xs"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-product-title"
      >
        <div class="w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-2xl">
          <div class="mb-4 flex items-center justify-between">
            <h2 id="create-product-title" class="font-editorial text-xl font-bold text-denim">
              Nuevo producto
            </h2>
            <button
              type="button"
              (click)="createModalOpen.set(false)"
              aria-label="Cerrar"
              class="rounded-lg p-1.5 text-ink-secondary hover:bg-cream-warm"
            >
              ✕
            </button>
          </div>

          <form (ngSubmit)="requestCreateConfirm()" #createForm="ngForm" class="space-y-3.5">
            <div>
              <label for="new-cat" class="mb-1 block text-xs font-medium text-denim">Categoría *</label>
              <select
                id="new-cat"
                name="category_id"
                required
                [(ngModel)]="newProduct.category_id"
                class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
              >
                <option value="">Selecciona una categoría</option>
                @for (cat of categories(); track cat.id) {
                  <option [value]="cat.id">{{ cat.name }}</option>
                }
              </select>
            </div>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label for="new-sku" class="mb-1 block text-xs font-medium text-denim">SKU *</label>
                <input
                  id="new-sku"
                  name="sku"
                  required
                  [(ngModel)]="newProduct.sku"
                  placeholder="LCDJ-JN-010"
                  class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label for="new-status" class="mb-1 block text-xs font-medium text-denim">Estado inicial</label>
                <select
                  id="new-status"
                  name="publication_status"
                  [(ngModel)]="newProduct.publication_status"
                  class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
                >
                  <option value="draft">Borrador</option>
                  <option value="published">Publicado</option>
                </select>
              </div>
            </div>

            <div>
              <label for="new-name" class="mb-1 block text-xs font-medium text-denim">Nombre *</label>
              <input
                id="new-name"
                name="name"
                required
                [(ngModel)]="newProduct.name"
                (ngModelChange)="syncSlugFromName($event)"
                placeholder="Jean Straight Índigo"
                class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label for="new-slug" class="mb-1 block text-xs font-medium text-denim">Slug (URL) *</label>
              <input
                id="new-slug"
                name="slug"
                required
                pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
                [(ngModel)]="newProduct.slug"
                placeholder="jean-straight-indigo"
                class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label for="new-desc" class="mb-1 block text-xs font-medium text-denim">Descripción</label>
              <textarea
                id="new-desc"
                name="description"
                rows="3"
                [(ngModel)]="newProduct.description"
                class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
              ></textarea>
            </div>

            <div class="flex justify-end gap-2 pt-2">
              <button
                type="button"
                (click)="createModalOpen.set(false)"
                class="rounded-xl border border-border-strong bg-white px-4 py-2 text-sm text-ink-secondary"
              >
                Cancelar
              </button>
              <button
                type="submit"
                [disabled]="createForm.invalid"
                class="rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white hover:bg-terracotta-hover disabled:opacity-50"
              >
                Continuar y confirmar
              </button>
            </div>
          </form>
        </div>
      </div>
    }

    <!-- Explicit Confirmation Dialog -->
    <app-confirm-dialog
      [open]="confirmOpen()"
      [title]="confirmTitle()"
      [message]="confirmMessage()"
      [details]="confirmDetails()"
      [confirmLabel]="confirmLabel()"
      [busy]="confirmBusy()"
      (confirmed)="executePendingConfirm()"
      (cancelled)="closeConfirm()"
    />
  `,
})
export class AdminInventoryPageComponent implements OnInit {
  readonly products = signal<ProductListItem[]>([]);
  readonly categories = signal<CategorySummary[]>([]);
  readonly loading = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly feedbackMessage = signal<string | null>(null);

  readonly page = signal(1);
  readonly totalPages = signal(1);
  readonly totalProducts = signal(0);

  readonly publishedCount = computed(
    () => this.products().filter((p) => p.publication_status === 'published').length
  );
  readonly nonPublishedCount = computed(
    () => this.products().filter((p) => p.publication_status !== 'published').length
  );
  readonly totalStockOnPage = computed(() =>
    this.products().reduce((sum, p) => sum + p.available_stock, 0)
  );

  search = '';
  selectedCategoryId = '';
  selectedStatus: '' | PublicationStatus = '';

  readonly createModalOpen = signal(false);
  newProduct: {
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

  readonly confirmOpen = signal(false);
  readonly confirmTitle = signal('');
  readonly confirmMessage = signal('');
  readonly confirmDetails = signal<string[]>([]);
  readonly confirmLabel = signal('Confirmar');
  readonly confirmBusy = signal(false);
  private pendingAction: (() => void) | null = null;

  constructor(
    readonly auth: AuthService,
    private readonly adminApi: AdminApiService,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    this.loadCategories();
    this.loadProducts();
  }

  loadCategories(): void {
    this.adminApi.listCategories({ page: 1, page_size: 100 }).subscribe({
      next: (res) => this.categories.set(res.items),
      error: () => {
        // Non-blocking
      },
    });
  }

  loadProducts(): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.adminApi
      .listProducts({
        page: this.page(),
        page_size: 20,
        search: this.search || undefined,
        category_id: this.selectedCategoryId || undefined,
        publication_status: this.selectedStatus || undefined,
      })
      .subscribe({
        next: (res) => {
          this.products.set(res.items);
          this.totalProducts.set(res.total);
          this.totalPages.set(Math.max(res.total_pages, 1));
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.loading.set(false);
          this.errorMessage.set(this.adminApi.extractErrorMessage(err));
        },
      });
  }

  applyFilters(): void {
    this.page.set(1);
    this.loadProducts();
  }

  resetFilters(): void {
    this.search = '';
    this.selectedCategoryId = '';
    this.selectedStatus = '';
    this.page.set(1);
    this.loadProducts();
  }

  goToPage(nextPage: number): void {
    this.page.set(nextPage);
    this.loadProducts();
  }

  openCreateModal(): void {
    this.newProduct = {
      category_id: this.categories()[0]?.id ?? '',
      sku: '',
      name: '',
      slug: '',
      description: '',
      publication_status: 'draft',
    };
    this.createModalOpen.set(true);
  }

  syncSlugFromName(name: string): void {
    this.newProduct.slug = name
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  requestCreateConfirm(): void {
    this.confirmTitle.set('Confirmar creación de producto');
    this.confirmMessage.set('Se registrará el nuevo producto en PostgreSQL.');
    this.confirmDetails.set([
      `Nombre: ${this.newProduct.name}`,
      `SKU: ${this.newProduct.sku}`,
      `Estado: ${this.statusLabel(this.newProduct.publication_status)}`,
    ]);
    this.confirmLabel.set('Crear producto');
    this.pendingAction = () => this.submitCreateProduct();
    this.confirmOpen.set(true);
  }

  private submitCreateProduct(): void {
    this.confirmBusy.set(true);
    this.adminApi
      .createProduct({
        category_id: this.newProduct.category_id,
        sku: this.newProduct.sku.trim(),
        name: this.newProduct.name.trim(),
        slug: this.newProduct.slug.trim(),
        description: this.newProduct.description.trim() || null,
        publication_status: this.newProduct.publication_status,
      })
      .subscribe({
        next: (created) => {
          this.confirmBusy.set(false);
          this.closeConfirm();
          this.createModalOpen.set(false);
          this.feedbackMessage.set(`Producto "${created.name}" creado correctamente.`);
          void this.router.navigate(['/admin/productos', created.id]);
        },
        error: (err: unknown) => {
          this.confirmBusy.set(false);
          this.closeConfirm();
          this.errorMessage.set(this.adminApi.extractErrorMessage(err));
        },
      });
  }

  requestQuickPublishToggle(item: ProductListItem): void {
    const nextStatus: PublicationStatus =
      item.publication_status === 'published' ? 'draft' : 'published';
    this.confirmTitle.set(
      nextStatus === 'published' ? 'Confirmar publicación' : 'Confirmar cambio a borrador'
    );
    this.confirmMessage.set(
      nextStatus === 'published'
        ? `¿Deseas publicar "${item.name}" en el catálogo público?`
        : `¿Deseas ocultar "${item.name}" pasándolo a borrador?`
    );
    this.confirmDetails.set([
      `SKU: ${item.sku}`,
      `Estado actual: ${this.statusLabel(item.publication_status)}`,
      `Nuevo estado: ${this.statusLabel(nextStatus)}`,
    ]);
    this.confirmLabel.set(nextStatus === 'published' ? 'Sí, publicar' : 'Sí, pasar a borrador');
    this.pendingAction = () => {
      this.confirmBusy.set(true);
      this.adminApi.updateProduct(item.id, { publication_status: nextStatus }).subscribe({
        next: () => {
          this.confirmBusy.set(false);
          this.closeConfirm();
          this.feedbackMessage.set(
            `Estado de "${item.name}" actualizado a ${this.statusLabel(nextStatus)}.`
          );
          this.loadProducts();
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

  executePendingConfirm(): void {
    this.pendingAction?.();
  }

  closeConfirm(): void {
    this.confirmOpen.set(false);
    this.pendingAction = null;
  }

  formatPrice(amount: string): string {
    return formatPab(amount);
  }

  imageUrl(item: ProductListItem): string {
    return resolveCatalogImageUrl(item.primary_image?.storage_path, item.slug || item.category_slug);
  }

  onImageError(event: Event, item: ProductListItem): void {
    const img = event.target as HTMLImageElement | null;
    if (!img || img.dataset['fallbackApplied']) {
      return;
    }
    img.dataset['fallbackApplied'] = 'true';
    img.src = getPlaceholderPhoto(item.category_slug || item.slug).url;
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
}
