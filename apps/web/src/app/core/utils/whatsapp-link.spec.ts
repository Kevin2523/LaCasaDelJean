import { InquiryCartItem } from '../models/inquiry-cart.models';
import {
  buildWhatsappInquiryMessage,
  buildWhatsappInquiryUrl,
  formatWhatsappDisplayNumber,
  sanitizeWhatsappNumber,
} from './whatsapp-link';

describe('whatsapp-link utils', () => {
  const sampleItems: InquiryCartItem[] = [
    {
      key: 'prod-1::var-32',
      productId: 'prod-1',
      productSlug: 'jean-clasico-indigo',
      productName: 'Jean Clásico Índigo & Algodón',
      categorySlug: 'jeans',
      sku: 'JCI-IND-32',
      variantId: 'var-32',
      size: '32',
      color: 'Índigo',
      unitPricePab: 39.95,
      currency: 'PAB',
      quantity: 2,
      imageUrl: '/media/jean.jpg',
      imageAlt: 'Jean Clásico Índigo',
    },
    {
      key: 'prod-2::var-m',
      productId: 'prod-2',
      productSlug: 'chaqueta-denim',
      productName: 'Chaqueta Denim Tradicional',
      categorySlug: 'damas',
      sku: 'CDT-AZU-M',
      variantId: 'var-m',
      size: 'M',
      color: 'Azul',
      unitPricePab: 54.5,
      currency: 'PAB',
      quantity: 1,
      imageUrl: '/media/chaqueta.jpg',
      imageAlt: 'Chaqueta Denim',
    },
  ];

  it('sanitizes and formats the Panama WhatsApp number', () => {
    expect(sanitizeWhatsappNumber('+507 6522-6428')).toBe('50765226428');
    expect(sanitizeWhatsappNumber('')).toBe('50765226428');
    expect(formatWhatsappDisplayNumber('50765226428')).toBe('+507 6522-6428');
  });

  it('builds a structured message with SKU, name, size, quantity, unit price and indicative total', () => {
    const message = buildWhatsappInquiryMessage(sampleItems);

    expect(message).toContain('Jean Clásico Índigo & Algodón');
    expect(message).toContain('SKU: JCI-IND-32');
    expect(message).toContain('Talla: 32');
    expect(message).toContain('Cantidad: 2');
    expect(message).toContain('B/. 39.95');
    expect(message).toContain('B/. 79.90');
    expect(message).toContain('Chaqueta Denim Tradicional');
    expect(message).toContain('SKU: CDT-AZU-M');
    expect(message).toContain('Total unidades: 3');
    expect(message).toContain('Total referencial: B/. 134.40');
    expect(message).toContain('sin reserva de stock ni pago en línea');
  });

  it('generates a valid percent-encoded wa.me/50765226428 URL', () => {
    const url = buildWhatsappInquiryUrl(sampleItems, '50765226428');

    expect(url.startsWith('https://wa.me/50765226428?text=')).toBeTrue();
    const encodedQuery = url.split('?text=')[1];
    expect(encodedQuery).not.toContain(' ');
    expect(encodedQuery).not.toContain('\n');
    expect(encodedQuery).toContain('%26'); // '&' in product name must be percent-encoded
    expect(decodeURIComponent(encodedQuery)).toBe(buildWhatsappInquiryMessage(sampleItems));
  });

  it('handles items without a confirmed price gracefully', () => {
    const unpriced: InquiryCartItem[] = [
      {
        ...sampleItems[0],
        unitPricePab: null,
        quantity: 1,
      },
    ];
    const message = buildWhatsappInquiryMessage(unpriced);
    expect(message).toContain('Precio por confirmar');
    expect(message).toContain('Total referencial parcial');
  });
});
