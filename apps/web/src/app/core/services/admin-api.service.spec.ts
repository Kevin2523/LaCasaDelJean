import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { API_BASE_URL } from '../config/api-config';
import { AdminApiService } from './admin-api.service';

describe('AdminApiService', () => {
  let service: AdminApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: API_BASE_URL, useValue: '' },
      ],
    });
    service = TestBed.inject(AdminApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('sends PAB currency when setting product price', () => {
    service
      .setCurrentPrice('prod-1', { amount_pab: '49.95', compare_at_pab: '59.95' })
      .subscribe();

    const req = httpMock.expectOne('/api/v1/admin/products/prod-1/prices');
    expect(req.request.method).toBe('POST');
    expect(req.request.body.currency).toBe('PAB');
    expect(req.request.body.amount_pab).toBe('49.95');
    req.flush({});
  });

  it('sends stock movement with idempotency key', () => {
    service
      .createStockMovement({
        variant_id: 'var-1',
        direction: 'in',
        movement_type: 'restock',
        quantity: 5,
        idempotency_key: 'idem-123',
        note: 'Conteo inicial',
      })
      .subscribe();

    const req = httpMock.expectOne('/api/v1/inventory/movements');
    expect(req.request.method).toBe('POST');
    expect(req.request.body.idempotency_key).toBe('idem-123');
    expect(req.request.body.quantity).toBe(5);
    req.flush({});
  });

  it('uploads product photograph as multipart FormData', () => {
    const file = new File(['fake-png'], 'jean.png', { type: 'image/png' });
    service
      .uploadProductImage('prod-1', file, { alt_text: 'Frente', is_primary: true })
      .subscribe();

    const req = httpMock.expectOne('/api/v1/admin/products/prod-1/images/upload');
    expect(req.request.method).toBe('POST');
    expect(req.request.body instanceof FormData).toBeTrue();
    req.flush({});
  });
});
