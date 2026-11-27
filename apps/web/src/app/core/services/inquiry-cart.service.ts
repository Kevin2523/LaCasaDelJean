import { Inject, Injectable, PLATFORM_ID, computed, signal } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import {
  INQUIRY_CART_MAX_QUANTITY,
  INQUIRY_CART_STORAGE_KEY,
  INQUIRY_CART_STORAGE_VERSION,
  InquiryCartItem,
  InquiryCartStoragePayload,
} from '../models/inquiry-cart.models';
import { calculateInquirySubtotal } from '../utils/whatsapp-link';

export type AddInquiryItemInput = Omit<InquiryCartItem, 'key'>;

export function buildInquiryItemKey(productId: string, variantId: string | null, size: string): string {
  return variantId ? `${productId}::${variantId}` : `${productId}::size:${size}`;
}

function clampQuantity(quantity: number): number {
  if (!Number.isFinite(quantity)) {
    return 1;
  }
  return Math.max(1, Math.min(INQUIRY_CART_MAX_QUANTITY, Math.floor(quantity)));
}

function isValidStoredItem(value: unknown): value is InquiryCartItem {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    typeof item['key'] === 'string' &&
    item['key'].length > 0 &&
    typeof item['productId'] === 'string' &&
    typeof item['productSlug'] === 'string' &&
    typeof item['productName'] === 'string' &&
    typeof item['sku'] === 'string' &&
    typeof item['size'] === 'string' &&
    typeof item['quantity'] === 'number' &&
    Number.isFinite(item['quantity']) &&
    item['quantity'] >= 1
  );
}

@Injectable({
  providedIn: 'root',
})
export class InquiryCartService {
  private readonly isBrowser: boolean;
  private readonly itemsSignal = signal<InquiryCartItem[]>([]);

  readonly items = this.itemsSignal.asReadonly();
  readonly isEmpty = computed(() => this.itemsSignal().length === 0);
  readonly totalUnits = computed(() =>
    this.itemsSignal().reduce((sum, item) => sum + item.quantity, 0)
  );
  readonly subtotalPab = computed(() => calculateInquirySubtotal(this.itemsSignal()));
  readonly hasUnpricedItems = computed(() =>
    this.itemsSignal().some((item) => item.unitPricePab === null || !Number.isFinite(item.unitPricePab))
  );

  constructor(@Inject(PLATFORM_ID) platformId: object) {
    this.isBrowser = isPlatformBrowser(platformId);
    this.hydrateFromStorage();
  }

  addItem(input: AddInquiryItemInput): InquiryCartItem {
    const key = buildInquiryItemKey(input.productId, input.variantId, input.size);
    const addedQty = clampQuantity(input.quantity);

    let resultItem: InquiryCartItem | null = null;

    this.itemsSignal.update((current) => {
      const existingIndex = current.findIndex((item) => item.key === key);
      if (existingIndex >= 0) {
        const existing = current[existingIndex];
        const updated: InquiryCartItem = {
          ...existing,
          ...input,
          key,
          quantity: clampQuantity(existing.quantity + addedQty),
        };
        resultItem = updated;
        return current.map((item, idx) => (idx === existingIndex ? updated : item));
      }
      const created: InquiryCartItem = {
        ...input,
        key,
        quantity: addedQty,
      };
      resultItem = created;
      return [...current, created];
    });

    this.persistToStorage();
    return resultItem!;
  }

  updateQuantity(key: string, quantity: number): void {
    if (!Number.isFinite(quantity) || quantity <= 0) {
      this.removeItem(key);
      return;
    }
    const clamped = clampQuantity(quantity);
    this.itemsSignal.update((current) =>
      current.map((item) => (item.key === key ? { ...item, quantity: clamped } : item))
    );
    this.persistToStorage();
  }

  increment(key: string): void {
    const existing = this.itemsSignal().find((item) => item.key === key);
    if (!existing) {
      return;
    }
    this.updateQuantity(key, existing.quantity + 1);
  }

  decrement(key: string): void {
    const existing = this.itemsSignal().find((item) => item.key === key);
    if (!existing) {
      return;
    }
    if (existing.quantity <= 1) {
      this.removeItem(key);
      return;
    }
    this.updateQuantity(key, existing.quantity - 1);
  }

  removeItem(key: string): void {
    this.itemsSignal.update((current) => current.filter((item) => item.key !== key));
    this.persistToStorage();
  }

  clear(): void {
    this.itemsSignal.set([]);
    this.persistToStorage();
  }

  private hydrateFromStorage(): void {
    if (!this.isBrowser) {
      return;
    }
    try {
      const raw = window.localStorage.getItem(INQUIRY_CART_STORAGE_KEY);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as Partial<InquiryCartStoragePayload>;
      if (parsed.version !== INQUIRY_CART_STORAGE_VERSION || !Array.isArray(parsed.items)) {
        window.localStorage.removeItem(INQUIRY_CART_STORAGE_KEY);
        return;
      }
      const validItems = parsed.items
        .filter(isValidStoredItem)
        .map((item) => ({
          ...item,
          quantity: clampQuantity(item.quantity),
          currency: item.currency || 'PAB',
          color: item.color || '',
          categorySlug: item.categorySlug || '',
          imageUrl: item.imageUrl || '',
          imageAlt: item.imageAlt || item.productName,
          unitPricePab:
            typeof item.unitPricePab === 'number' && Number.isFinite(item.unitPricePab)
              ? item.unitPricePab
              : null,
        }));
      this.itemsSignal.set(validItems);
    } catch {
      try {
        window.localStorage.removeItem(INQUIRY_CART_STORAGE_KEY);
      } catch {
        // Ignore storage errors in restricted environments
      }
      this.itemsSignal.set([]);
    }
  }

  private persistToStorage(): void {
    if (!this.isBrowser) {
      return;
    }
    try {
      const payload: InquiryCartStoragePayload = {
        version: INQUIRY_CART_STORAGE_VERSION,
        updatedAt: new Date().toISOString(),
        items: this.itemsSignal(),
      };
      window.localStorage.setItem(INQUIRY_CART_STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // Gracefully degrade to in-memory state if localStorage is full or blocked
    }
  }
}
