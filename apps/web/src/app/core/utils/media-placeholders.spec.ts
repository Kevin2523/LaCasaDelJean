import { getPlaceholderPhoto, resolveCatalogImageUrl } from './media-placeholders';

describe('resolveCatalogImageUrl', () => {
  it('resolves valid relative FastAPI storage_path to /media/<path>', () => {
    expect(resolveCatalogImageUrl('products/lcdj-001/main.webp', 'jeans-slim')).toBe(
      '/media/products/lcdj-001/main.webp'
    );
  });

  it('preserves external HTTP(S) URLs as-is', () => {
    const external = 'https://cdn.example.com/images/jean.webp';
    expect(resolveCatalogImageUrl(external, 'jeans-slim')).toBe(external);
  });

  it('falls back to placeholder for null, empty, leading slash, traversal, or invalid schemes', () => {
    const fallback = getPlaceholderPhoto('jeans-slim').url;
    expect(resolveCatalogImageUrl(null, 'jeans-slim')).toBe(fallback);
    expect(resolveCatalogImageUrl('   ', 'jeans-slim')).toBe(fallback);
    expect(resolveCatalogImageUrl('/products/foo/main.webp', 'jeans-slim')).toBe(fallback);
    expect(resolveCatalogImageUrl('../secrets/env.png', 'jeans-slim')).toBe(fallback);
    expect(resolveCatalogImageUrl('products/../secret.webp', 'jeans-slim')).toBe(fallback);
    expect(resolveCatalogImageUrl('products\\foo\\main.webp', 'jeans-slim')).toBe(fallback);
    expect(resolveCatalogImageUrl('javascript:alert(1)', 'jeans-slim')).toBe(fallback);
  });
});
