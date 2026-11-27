import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { API_BASE_URL } from '../config/api-config';
import { formatPab, getDiscountPercent } from '../utils/format-pab';
import { CatalogApiService } from './catalog-api.service';

describe('CatalogApiService & PAB formatting', () => {
  let service: CatalogApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: 'http://api.test' },
      ],
    });
    service = TestBed.inject(CatalogApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should query /api/v1/products with PAB price filters and sort_by', () => {
    service
      .listProducts({
        page: 2,
        page_size: 12,
        category_slug: 'jeans-slim',
        search: 'indigo',
        size: '32',
        min_price_pab: 20,
        max_price_pab: 60,
        in_stock: true,
        sort_by: 'price_asc',
      })
      .subscribe((res) => {
        expect(res.total).toBe(1);
        expect(res.items[0].current_price?.currency).toBe('PAB');
      });

    const req = httpMock.expectOne((r) => r.url === 'http://api.test/api/v1/products');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('category_slug')).toBe('jeans-slim');
    expect(req.request.params.get('min_price_pab')).toBe('20');
    expect(req.request.params.get('max_price_pab')).toBe('60');
    expect(req.request.params.get('in_stock')).toBe('true');
    expect(req.request.params.get('sort_by')).toBe('price_asc');

    req.flush({
      items: [
        {
          id: 'p1',
          category_id: 'c1',
          category_name: 'Jeans Slim',
          category_slug: 'jeans-slim',
          sku: 'LCDJ-001',
          name: 'Jean Slim Índigo',
          slug: 'jean-slim-indigo',
          description: null,
          publication_status: 'published',
          published_at: '2026-01-01T00:00:00Z',
          current_price: {
            id: 'pr1',
            product_id: 'p1',
            variant_id: null,
            amount_pab: '39.95',
            compare_at_pab: '49.95',
            currency: 'PAB',
            is_current: true,
            valid_from: '2026-01-01T00:00:00Z',
            valid_to: null,
            created_at: '2026-01-01T00:00:00Z',
          },
          primary_image: null,
          available_stock: 10,
          in_stock: true,
          published_variant_count: 2,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
      page: 2,
      page_size: 12,
      total_pages: 1,
    });
  });

  it('should format PAB amounts as B/. and compute discount percentage', () => {
    expect(formatPab('39.95', 'PAB')).toContain('B/.');
    expect(formatPab('39.95', 'PAB')).toContain('39.95');
    expect(formatPab(null)).toBe('Precio por confirmar');
    expect(getDiscountPercent('40.00', '50.00')).toBe(20);
  });
});
