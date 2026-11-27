import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CategorySummary } from '../../../core/models/catalog.models';
import { AdminApiService } from '../../../core/services/admin-api.service';
import { AuthService } from '../../../core/services/auth.service';
import { ConfirmDialogComponent } from '../components/confirm-dialog.component';

@Component({
  selector: 'app-admin-categories-page',
  standalone: true,
  imports: [CommonModule, FormsModule, ConfirmDialogComponent],
  template: `
    <div class="mx-auto max-w-[1120px] space-y-6">
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
            Estructura del catálogo
          </p>
          <h1 class="mt-1 font-editorial text-2xl font-bold text-denim sm:text-3xl">
            Categorías
          </h1>
        </div>
        @if (auth.canWrite()) {
          <button
            type="button"
            (click)="startCreate()"
            class="rounded-xl bg-terracotta px-4 py-2.5 text-sm font-semibold text-white hover:bg-terracotta-hover"
          >
            + Nueva categoría
          </button>
        }
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

      <!-- Category Form (Create/Edit) -->
      @if (formOpen() && auth.canWrite()) {
        <section class="rounded-2xl border border-border bg-surface p-5">
          <h2 class="font-editorial text-lg font-bold text-denim">
            {{ editingId() ? 'Editar categoría' : 'Crear categoría' }}
          </h2>
          <form (ngSubmit)="requestSaveConfirm()" #catForm="ngForm" class="mt-4 grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            <div>
              <label for="cat-name" class="mb-1 block text-xs font-medium text-denim">Nombre *</label>
              <input
                id="cat-name"
                name="name"
                required
                [(ngModel)]="form.name"
                (ngModelChange)="!editingId() && syncSlug($event)"
                class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label for="cat-slug" class="mb-1 block text-xs font-medium text-denim">Slug *</label>
              <input
                id="cat-slug"
                name="slug"
                required
                pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
                [(ngModel)]="form.slug"
                class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label for="cat-order" class="mb-1 block text-xs font-medium text-denim">Orden</label>
              <input
                id="cat-order"
                name="display_order"
                type="number"
                min="0"
                [(ngModel)]="form.display_order"
                class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
              />
            </div>
            <div class="flex items-end">
              <label class="inline-flex items-center gap-2 text-sm text-denim">
                <input type="checkbox" name="is_active" [(ngModel)]="form.is_active" class="h-4 w-4 rounded" />
                Categoría activa (visible en tienda)
              </label>
            </div>
            <div class="sm:col-span-2">
              <label for="cat-desc" class="mb-1 block text-xs font-medium text-denim">Descripción</label>
              <textarea
                id="cat-desc"
                name="description"
                rows="2"
                [(ngModel)]="form.description"
                class="w-full rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
              ></textarea>
            </div>
            <div class="flex justify-end gap-2 sm:col-span-2">
              <button
                type="button"
                (click)="formOpen.set(false)"
                class="rounded-xl border border-border-strong bg-white px-4 py-2 text-sm text-ink-secondary"
              >
                Cancelar
              </button>
              <button
                type="submit"
                [disabled]="catForm.invalid"
                class="rounded-xl bg-denim px-4 py-2 text-sm font-semibold text-white hover:bg-denim-deep disabled:opacity-50"
              >
                Guardar cambios
              </button>
            </div>
          </form>
        </section>
      }

      <!-- Categories Table -->
      <section class="overflow-hidden rounded-2xl border border-border bg-surface">
        @if (loading()) {
          <div class="p-8 text-center text-sm text-ink-secondary">Cargando categorías...</div>
        } @else {
          <div class="overflow-x-auto">
            <table class="w-full min-w-[600px] border-collapse text-left text-sm">
              <thead class="border-b border-border bg-cream-warm/70 text-xs font-semibold uppercase tracking-wider text-ink-secondary">
                <tr>
                  <th class="px-4 py-3">Nombre</th>
                  <th class="px-4 py-3">Slug</th>
                  <th class="px-4 py-3">Orden</th>
                  <th class="px-4 py-3">Estado</th>
                  @if (auth.canWrite()) {
                    <th class="px-4 py-3 text-right">Acciones</th>
                  }
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                @for (cat of categories(); track cat.id) {
                  <tr class="hover:bg-cream/60">
                    <td class="px-4 py-3 font-semibold text-denim">{{ cat.name }}</td>
                    <td class="px-4 py-3 text-ink-secondary">{{ cat.slug }}</td>
                    <td class="px-4 py-3 text-ink-secondary">{{ cat.display_order }}</td>
                    <td class="px-4 py-3">
                      <span
                        class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold"
                        [ngClass]="cat.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'"
                      >
                        {{ cat.is_active ? 'Activa' : 'Inactiva' }}
                      </span>
                    </td>
                    @if (auth.canWrite()) {
                      <td class="px-4 py-3 text-right">
                        <button
                          type="button"
                          (click)="startEdit(cat)"
                          class="rounded-lg border border-border-strong bg-white px-3 py-1.5 text-xs font-semibold text-denim hover:bg-denim-soft"
                        >
                          Editar
                        </button>
                      </td>
                    }
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
    </div>

    <app-confirm-dialog
      [open]="confirmOpen()"
      [title]="editingId() ? 'Confirmar actualización de categoría' : 'Confirmar nueva categoría'"
      [message]="'Se guardarán los cambios en la base de datos.'"
      [details]="['Nombre: ' + form.name, 'Slug: ' + form.slug, 'Activa: ' + (form.is_active ? 'Sí' : 'No')]"
      [busy]="saving()"
      (confirmed)="submitCategory()"
      (cancelled)="confirmOpen.set(false)"
    />
  `,
})
export class AdminCategoriesPageComponent implements OnInit {
  readonly categories = signal<CategorySummary[]>([]);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly feedbackMessage = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editingId = signal<string | null>(null);
  readonly confirmOpen = signal(false);

  form = {
    name: '',
    slug: '',
    description: '',
    display_order: 0,
    is_active: true,
  };

  constructor(
    readonly auth: AuthService,
    private readonly adminApi: AdminApiService
  ) {}

  ngOnInit(): void {
    this.loadCategories();
  }

  loadCategories(): void {
    this.loading.set(true);
    this.adminApi.listCategories({ page: 1, page_size: 100 }).subscribe({
      next: (res) => {
        this.categories.set(res.items);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.errorMessage.set(this.adminApi.extractErrorMessage(err));
      },
    });
  }

  startCreate(): void {
    this.editingId.set(null);
    this.form = { name: '', slug: '', description: '', display_order: 0, is_active: true };
    this.formOpen.set(true);
  }

  startEdit(cat: CategorySummary): void {
    this.editingId.set(cat.id);
    this.form = {
      name: cat.name,
      slug: cat.slug,
      description: cat.description ?? '',
      display_order: cat.display_order,
      is_active: cat.is_active,
    };
    this.formOpen.set(true);
  }

  syncSlug(name: string): void {
    this.form.slug = name
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  requestSaveConfirm(): void {
    this.confirmOpen.set(true);
  }

  submitCategory(): void {
    this.saving.set(true);
    this.errorMessage.set(null);
    const id = this.editingId();
    const payload = {
      name: this.form.name.trim(),
      slug: this.form.slug.trim(),
      description: this.form.description.trim() || null,
      display_order: Number(this.form.display_order) || 0,
      is_active: this.form.is_active,
    };

    const req$ = id ? this.adminApi.updateCategory(id, payload) : this.adminApi.createCategory(payload);
    req$.subscribe({
      next: (saved) => {
        this.saving.set(false);
        this.confirmOpen.set(false);
        this.formOpen.set(false);
        this.feedbackMessage.set(`Categoría "${saved.name}" guardada correctamente.`);
        this.loadCategories();
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.confirmOpen.set(false);
        this.errorMessage.set(this.adminApi.extractErrorMessage(err));
      },
    });
  }
}
