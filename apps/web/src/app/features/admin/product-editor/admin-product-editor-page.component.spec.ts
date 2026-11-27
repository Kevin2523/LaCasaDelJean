import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { API_BASE_URL } from '../../../core/config/api-config';
import { ProductDetail } from '../../../core/models/catalog.models';
import { getPlaceholderPhoto } from '../../../core/utils/media-placeholders';
import { AdminProductEditorPageComponent } from './admin-product-editor-page.component';

describe('AdminProductEditorPageComponent image fallback', () => {
  let component: AdminProductEditorPageComponent;

  const sampleProduct: ProductDetail = {
    id: 'prod-1',
    category_id: 'cat-1',
    category: {
      id: 'cat-1',
      name: 'Damas',
      slug: 'damas',
      description: null,
      parent_id: null,
      display_order: 1,
      is_active: true,
      created_at: '2026-11-27T00:00:00Z',
      updated_at: '2026-11-27T00:00:00Z',
    },
    sku: 'LCDJ-002',
    name: 'Jean Tiro Alto Slim',
    slug: 'jean-tiro-alto-slim',
    description: null,
    publication_status: 'published',
    published_at: null,
    current_price: null,
    variants: [],
    images: [],
    created_at: '2026-11-27T00:00:00Z',
    updated_at: '2026-11-27T00:00:00Z',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [AdminProductEditorPageComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: API_BASE_URL, useValue: '' },
      ],
    });
    const fixture = TestBed.createComponent(AdminProductEditorPageComponent);
    component = fixture.componentInstance;
  });

  it('applies licensed placeholder fallback once on gallery image error and prevents loops', () => {
    const img = document.createElement('img');
    img.src = 'http://localhost/media/products/missing/gallery.jpg';
    const expectedFallback = getPlaceholderPhoto(sampleProduct.category.slug).url;

    component.onImageError({ target: img } as unknown as Event, sampleProduct);

    expect(img.dataset['fallbackApplied']).toBe('true');
    expect(img.src).toBe(expectedFallback);

    // Second error event must be ignored to avoid loops
    img.src = 'http://localhost/already-handled.jpg';
    component.onImageError({ target: img } as unknown as Event, sampleProduct);
    expect(img.src).toBe('http://localhost/already-handled.jpg');
  });
});
