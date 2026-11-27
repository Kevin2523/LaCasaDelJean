import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { WHATSAPP_NUMBER } from '../../core/config/api-config';
import { InquiryCartService } from '../../core/services/inquiry-cart.service';
import { InquiryCartPageComponent } from './inquiry-cart-page.component';

describe('InquiryCartPageComponent', () => {
  beforeEach(async () => {
    window.localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [InquiryCartPageComponent],
      providers: [
        provideRouter([]),
        { provide: WHATSAPP_NUMBER, useValue: '50765226428' },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it('renders empty state when cart has no items', () => {
    const fixture = TestBed.createComponent(InquiryCartPageComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Aún no has agregado prendas');
    expect(el.querySelector('a[href^="https://wa.me/"]')).toBeNull();
  });

  it('renders items, updates quantities, and generates valid wa.me link', () => {
    const cart = TestBed.inject(InquiryCartService);
    cart.addItem({
      productId: 'p1',
      productSlug: 'jean-slim',
      productName: 'Jean Tiro Alto Slim',
      categorySlug: 'jeans',
      sku: 'JTAS-30',
      variantId: 'v30',
      size: '30',
      color: 'Índigo',
      unitPricePab: 42.0,
      currency: 'PAB',
      quantity: 2,
      imageUrl: '/media/slim.jpg',
      imageAlt: 'Jean Tiro Alto Slim',
    });

    const fixture = TestBed.createComponent(InquiryCartPageComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent).toContain('Jean Tiro Alto Slim');
    expect(el.textContent).toContain('JTAS-30');
    expect(el.textContent).toContain('B/. 84.00');

    const waLink = el.querySelector('a[href^="https://wa.me/50765226428?text="]') as HTMLAnchorElement | null;
    expect(waLink).toBeTruthy();
    expect(decodeURIComponent(waLink!.href)).toContain('Total referencial: B/. 84.00');

    // Click increment button
    const incBtn = el.querySelector('button[aria-label^="Aumentar cantidad"]') as HTMLButtonElement;
    incBtn.click();
    fixture.detectChanges();
    expect(cart.totalUnits()).toBe(3);
    expect(el.textContent).toContain('B/. 126.00');

    // Click remove button
    const removeBtn = el.querySelector('button[aria-label^="Quitar "]') as HTMLButtonElement;
    removeBtn.click();
    fixture.detectChanges();
    expect(cart.isEmpty()).toBeTrue();
    expect(el.textContent).toContain('Aún no has agregado prendas');
  });
});
