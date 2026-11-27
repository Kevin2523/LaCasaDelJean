import { PLATFORM_ID } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  INQUIRY_CART_MAX_QUANTITY,
  INQUIRY_CART_STORAGE_KEY,
  INQUIRY_CART_STORAGE_VERSION,
} from '../models/inquiry-cart.models';
import { AddInquiryItemInput, InquiryCartService } from './inquiry-cart.service';

describe('InquiryCartService', () => {
  const baseItem: AddInquiryItemInput = {
    productId: 'prod-1',
    productSlug: 'jean-clasico',
    productName: 'Jean Clásico',
    categorySlug: 'jeans',
    sku: 'JC-32',
    variantId: 'var-32',
    size: '32',
    color: 'Índigo',
    unitPricePab: 39.95,
    currency: 'PAB',
    quantity: 1,
    imageUrl: '/media/jean.jpg',
    imageAlt: 'Jean Clásico',
  };

  beforeEach(() => {
    window.localStorage.clear();
    TestBed.configureTestingModule({
      providers: [{ provide: PLATFORM_ID, useValue: 'browser' }],
    });
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it('adds items, merges duplicate variants, updates quantities, and removes items', () => {
    const service = TestBed.inject(InquiryCartService);

    const added = service.addItem(baseItem);
    expect(service.items().length).toBe(1);
    expect(service.totalUnits()).toBe(1);
    expect(service.subtotalPab()).toBeCloseTo(39.95, 2);

    // Adding same product + variant increments quantity
    service.addItem({ ...baseItem, quantity: 2 });
    expect(service.items().length).toBe(1);
    expect(service.totalUnits()).toBe(3);
    expect(service.subtotalPab()).toBeCloseTo(119.85, 2);

    service.decrement(added.key);
    expect(service.totalUnits()).toBe(2);

    service.increment(added.key);
    expect(service.totalUnits()).toBe(3);

    service.updateQuantity(added.key, 999);
    expect(service.totalUnits()).toBe(INQUIRY_CART_MAX_QUANTITY);

    service.removeItem(added.key);
    expect(service.isEmpty()).toBeTrue();
  });

  it('persists cart to localStorage and hydrates on reload', () => {
    const service = TestBed.inject(InquiryCartService);
    service.addItem({ ...baseItem, quantity: 2 });

    const stored = window.localStorage.getItem(INQUIRY_CART_STORAGE_KEY);
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed.version).toBe(INQUIRY_CART_STORAGE_VERSION);
    expect(parsed.items.length).toBe(1);
    expect(parsed.items[0].quantity).toBe(2);

    // Simulate fresh service instance after page reload
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [{ provide: PLATFORM_ID, useValue: 'browser' }],
    });
    const reloaded = TestBed.inject(InquiryCartService);
    expect(reloaded.items().length).toBe(1);
    expect(reloaded.totalUnits()).toBe(2);
    expect(reloaded.items()[0].sku).toBe('JC-32');
  });

  it('recovers cleanly from corrupted localStorage data', () => {
    window.localStorage.setItem(INQUIRY_CART_STORAGE_KEY, '{not-valid-json');

    const service = TestBed.inject(InquiryCartService);
    expect(service.isEmpty()).toBeTrue();
    expect(window.localStorage.getItem(INQUIRY_CART_STORAGE_KEY)).toBeNull();
  });
});
