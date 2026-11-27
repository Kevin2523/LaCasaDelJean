import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-state-banner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      [attr.role]="variant === 'error' ? 'alert' : 'status'"
      class="mx-auto max-w-xl rounded-2xl border p-8 text-center"
      [ngClass]="
        variant === 'error'
          ? 'border-[#fecaca] bg-[#fef2f2] text-[#7f1d1d]'
          : 'border-border bg-surface text-ink'
      "
    >
      <div
        class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full"
        [ngClass]="
          variant === 'error'
            ? 'bg-[#fee2e2] text-[#991b1b]'
            : 'bg-denim-soft text-denim'
        "
      >
        @if (variant === 'error') {
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z" />
          </svg>
        } @else {
          <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="m21 21-4.35-4.35m0 0A7.5 7.5 0 1 0 5.65 5.65a7.5 7.5 0 0 0 11 11Z" />
          </svg>
        }
      </div>

      <h3 class="font-editorial text-xl font-bold">{{ title }}</h3>
      <p class="mt-2 text-sm opacity-90">{{ message }}</p>

      @if (actionLabel) {
        <button
          type="button"
          (click)="action.emit()"
          class="mt-5 inline-flex items-center justify-center rounded-full px-5 py-2.5 text-sm font-semibold transition-colors"
          [ngClass]="
            variant === 'error'
              ? 'bg-[#991b1b] text-white hover:bg-[#7f1d1d]'
              : 'bg-denim text-white hover:bg-denim-deep'
          "
        >
          {{ actionLabel }}
        </button>
      }
    </div>
  `,
})
export class StateBannerComponent {
  @Input() variant: 'empty' | 'error' = 'empty';
  @Input({ required: true }) title = '';
  @Input({ required: true }) message = '';
  @Input() actionLabel = '';
  @Output() action = new EventEmitter<void>();
}
