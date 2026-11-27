import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { WHATSAPP_NUMBER } from '../../core/config/api-config';
import { ProductDetail } from '../../core/models/catalog.models';
import { CatalogApiService } from '../../core/services/catalog-api.service';
import { InquiryCartService } from '../../core/services/inquiry-cart.service';
import { ProductDetailPageComponent } from './product-detail-page.component';

describe('ProductDetailPageComponent (inquiry cart integration)', () => {
  const mockProduct: ProductDetail = {
    id: 'prod-1',
    category_id: 'cat-1',
    category: {
      id: 'cat-1',
      name: 'Jeans',
      slug: 'jeans',
      description: null,
      parent_id: null,
      display_order: 1,
      is_active: true,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    sku: 'JCI-BASE',
    name: 'Jean Clásico Índigo',
    slug: 'jean-clasico-indigo',
    description: 'Corte recto clásico.',
    publication_status: 'published',
    published_at: '2026-01-01T00:00:00Z',
    current_price: {
      id: 'pr-1',
      product_id: 'prod-1',
      variant_id: null,
      amount_pab: '39.95',
      compare_at_pab: null,
      currency: 'PAB',
      is_current: true,
      valid_from: '2026-01-01T00:00:00Z',
      valid_to: null,
      created_at: '2026-01-01T00:00:00Z',
    },
    variants: [
      {
        id: 'var-30',
        product_id: 'prod-1',
        sku: 'JCI-IND-30',
        size: '30',
        color: 'Índigo',
        color_hex: '#162d4c',
        barcode: null,
        publication_status: 'published',
        current_price: null,
        stock: {
          quantity: 5,
          reserved_quantity: 0,
          available_quantity: 5,
          in_stock: true,
          version: 1,
          updated_at: '2026-01-01T00:00:00Z',
        },
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
      {
        id: 'var-32',
        product_id: 'prod-1',
        sku: 'JCI-IND-32',
        size: '32',
        color: 'Índigo',
        color_hex: '#162d4c',
        barcode: null,
        publication_status: 'published',
        current_price: null,
        stock: {
          quantity: 4,
          reserved_quantity: 0,
          available_quantity: 4,
          in_stock: true,
          version: 1,
          updated_at: '2026-01-01T00:00:00Z',
        },
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ],
    images: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };

  beforeEach(async () => {
    window.localStorage.clear();
    const apiSpy = jasmine.createSpyObj<CatalogApiService>('CatalogApiService', [
      'getProductBySlug',
      'extractErrorMessage',
    ]);
    apiSpy.getProductBySlug.and.returnValue(of(mockProduct));

    await TestBed.configureTestingModule({
      imports: [ProductDetailPageComponent],
      providers: [
        provideRouter([]),
        { provide: CatalogApiService, useValue: apiSpy },
        { provide: WHATSAPP_NUMBER, useValue: '50765226428' },
        {
          provide: ActivatedRoute,
          useValue: { paramMap: of(convertToParamMap({ slug: 'jean-clasico-indigo' })) },
        },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it('selects size and quantity, adds item to inquiry cart, and exposes direct wa.me link', () => {
    const fixture = TestBed.createComponent(ProductDetailPageComponent);
    fixture.detectChanges();

    const component = fixture.componentInstance;
    const cart = TestBed.inject(InquiryCartService);

    // Select size 32 and increment quantity to 2
    component.selectVariant(mockProduct.variants[1]);
    component.incrementQuantity();
    component.addToInquiryCart();
    fixture.detectChanges();

    expect(cart.totalUnits()).toBe(2);
    expect(cart.items()[0].sku).toBe('JCI-IND-32');
    expect(cart.items()[0].size).toBe('32');

    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Ver lista de consulta (2)');

    const directWa = el.querySelector('a[href^="https://wa.me/50765226428?text="]') as HTMLAnchorElement | null;
    expect(directWa).toBeTruthy();
    expect(decodeURIComponent(directWa!.href)).toContain('JCI-IND-32');
    expect(decodeURIComponent(directWa!.href)).toContain('Cantidad: 2');
  });
});
