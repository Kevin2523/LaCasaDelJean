import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { API_BASE_URL } from '../../../core/config/api-config';
import { ProductListItem } from '../../../core/models/catalog.models';
import { getPlaceholderPhoto } from '../../../core/utils/media-placeholders';
import { AdminInventoryPageComponent } from './admin-inventory-page.component';

describe('AdminInventoryPageComponent image fallback', () => {
  let component: AdminInventoryPageComponent;

  const sampleProduct: ProductListItem = {
    id: 'prod-1',
    category_id: 'cat-1',
    category_name: 'Jeans',
    category_slug: 'jeans',
    sku: 'LCDJ-001',
    name: 'Jean Clásico Índigo',
    slug: 'jean-clasico-indigo',
    description: null,
    publication_status: 'published',
    published_at: null,
    current_price: null,
    primary_image: {
      id: 'img-1',
      product_id: 'prod-1',
      variant_id: null,
      storage_path: 'products/missing/seed.jpg',
      original_filename: 'seed.jpg',
      mime_type: 'image/jpeg',
      size_bytes: 1024,
      width: 800,
      height: 1000,
      sha256: 'a'.repeat(64),
      alt_text: 'Jean',
      display_order: 0,
      is_primary: true,
      created_at: '2026-11-27T00:00:00Z',
    },
    available_stock: 5,
    in_stock: true,
    published_variant_count: 1,
    created_at: '2026-11-27T00:00:00Z',
    updated_at: '2026-11-27T00:00:00Z',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [AdminInventoryPageComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: API_BASE_URL, useValue: '' },
      ],
    });
    const fixture = TestBed.createComponent(AdminInventoryPageComponent);
    component = fixture.componentInstance;
  });

  it('applies licensed placeholder fallback once on /media error and prevents loops', () => {
    const img = document.createElement('img');
    img.src = 'http://localhost/media/products/missing/seed.jpg';
    const expectedFallback = getPlaceholderPhoto(sampleProduct.category_slug).url;

    component.onImageError({ target: img } as unknown as Event, sampleProduct);

    expect(img.dataset['fallbackApplied']).toBe('true');
    expect(img.src).toBe(expectedFallback);

    // Simulate a second error event; src must not be overwritten again
    img.src = 'http://localhost/already-handled.jpg';
    component.onImageError({ target: img } as unknown as Event, sampleProduct);
    expect(img.src).toBe('http://localhost/already-handled.jpg');
  });
});
