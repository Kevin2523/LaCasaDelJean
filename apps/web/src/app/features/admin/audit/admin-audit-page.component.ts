import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuditEvent } from '../../../core/models/admin.models';
import { AdminApiService } from '../../../core/services/admin-api.service';

@Component({
  selector: 'app-admin-audit-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="mx-auto max-w-[1200px] space-y-6">
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.16em] text-terracotta">
          Solo Administradores
        </p>
        <h1 class="mt-1 font-editorial text-2xl font-bold text-denim sm:text-3xl">
          Bitácora de auditoría
        </h1>
      </div>

      <section class="rounded-2xl border border-border bg-surface p-4">
        <form (ngSubmit)="loadEvents(1)" class="flex flex-wrap items-end gap-3">
          <div>
            <label for="audit-entity" class="mb-1 block text-xs font-medium text-ink-secondary">Entidad</label>
            <select
              id="audit-entity"
              name="entity_type"
              [(ngModel)]="entityType"
              class="rounded-xl border border-border-strong bg-white px-3 py-2 text-sm"
            >
              <option value="">Todas</option>
              <option value="product">product</option>
              <option value="category">category</option>
              <option value="variant">variant</option>
              <option value="price">price</option>
              <option value="image">image</option>
              <option value="stock_movement">stock_movement</option>
              <option value="auth_session">auth_session</option>
            </select>
          </div>
          <button
            type="submit"
            class="rounded-xl bg-denim px-4 py-2 text-sm font-semibold text-white hover:bg-denim-deep"
          >
            Filtrar
          </button>
        </form>
      </section>

      @if (errorMessage(); as err) {
        <div role="alert" class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {{ err }}
        </div>
      }

      <section class="overflow-hidden rounded-2xl border border-border bg-surface">
        @if (loading()) {
          <div class="p-8 text-center text-sm text-ink-secondary">Cargando eventos de auditoría...</div>
        } @else if (events().length === 0) {
          <div class="p-8 text-center text-sm text-ink-secondary">No hay eventos registrados.</div>
        } @else {
          <div class="overflow-x-auto">
            <table class="w-full min-w-[720px] border-collapse text-left text-xs">
              <thead class="border-b border-border bg-cream-warm/70 font-semibold uppercase tracking-wider text-ink-secondary">
                <tr>
                  <th class="px-4 py-3">Fecha (UTC)</th>
                  <th class="px-4 py-3">Entidad</th>
                  <th class="px-4 py-3">Acción</th>
                  <th class="px-4 py-3">Request ID</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                @for (ev of events(); track ev.id) {
                  <tr class="hover:bg-cream/60">
                    <td class="px-4 py-3 text-ink-secondary">{{ ev.created_at | date:'short' }}</td>
                    <td class="px-4 py-3 font-semibold text-denim">{{ ev.entity_type }}</td>
                    <td class="px-4 py-3">
                      <span class="rounded-full bg-denim-soft px-2.5 py-0.5 font-semibold text-denim">
                        {{ ev.action }}
                      </span>
                    </td>
                    <td class="px-4 py-3 font-mono text-ink-muted">{{ ev.request_id || '—' }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
    </div>
  `,
})
export class AdminAuditPageComponent implements OnInit {
  readonly events = signal<AuditEvent[]>([]);
  readonly loading = signal(false);
  readonly errorMessage = signal<string | null>(null);
  entityType = '';

  constructor(private readonly adminApi: AdminApiService) {}

  ngOnInit(): void {
    this.loadEvents(1);
  }

  loadEvents(page: number): void {
    this.loading.set(true);
    this.errorMessage.set(null);
    this.adminApi
      .listAuditEvents({
        entity_type: this.entityType || undefined,
        page,
        page_size: 30,
      })
      .subscribe({
        next: (res) => {
          this.events.set(res.items);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.loading.set(false);
          this.errorMessage.set(this.adminApi.extractErrorMessage(err));
        },
      });
  }
}
