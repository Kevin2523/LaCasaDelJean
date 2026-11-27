import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (open) {
      <div
        class="fixed inset-0 z-50 flex items-center justify-center bg-denim-deep/60 p-4 backdrop-blur-xs"
        role="dialog"
        aria-modal="true"
        [attr.aria-labelledby]="'confirm-dialog-title'"
      >
        <div class="w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-2xl">
          <div class="mb-3 flex items-start gap-3">
            <div
              class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
              [ngClass]="
                tone === 'danger'
                  ? 'bg-red-100 text-red-700'
                  : 'bg-terracotta-soft text-terracotta'
              "
            >
              <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"
                />
              </svg>
            </div>
            <div>
              <h3 id="confirm-dialog-title" class="font-editorial text-lg font-bold text-denim">
                {{ title }}
              </h3>
              <p class="mt-1 text-sm text-ink-secondary">{{ message }}</p>
            </div>
          </div>

          @if (details.length > 0) {
            <ul class="mb-4 space-y-1 rounded-xl border border-border bg-cream px-3.5 py-2.5 text-xs text-ink-secondary">
              @for (item of details; track item) {
                <li>• {{ item }}</li>
              }
            </ul>
          }

          <div class="flex flex-wrap justify-end gap-2.5 pt-2">
            <button
              type="button"
              (click)="cancelled.emit()"
              [disabled]="busy"
              class="rounded-lg border border-border-strong bg-white px-4 py-2 text-sm font-medium text-ink-secondary hover:bg-cream-warm disabled:opacity-50"
            >
              {{ cancelLabel }}
            </button>
            <button
              type="button"
              (click)="confirmed.emit()"
              [disabled]="busy"
              class="rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors disabled:opacity-50"
              [ngClass]="
                tone === 'danger'
                  ? 'bg-red-700 hover:bg-red-800'
                  : 'bg-terracotta hover:bg-terracotta-hover'
              "
            >
              {{ busy ? 'Procesando...' : confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    }
  `,
})
export class ConfirmDialogComponent {
  @Input() open = false;
  @Input() title = 'Confirmar acción';
  @Input() message = '¿Deseas continuar con esta operación?';
  @Input() details: string[] = [];
  @Input() confirmLabel = 'Confirmar';
  @Input() cancelLabel = 'Cancelar';
  @Input() tone: 'default' | 'danger' = 'default';
  @Input() busy = false;

  @Output() confirmed = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();
}
