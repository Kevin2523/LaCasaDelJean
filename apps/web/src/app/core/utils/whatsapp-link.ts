import { InquiryCartItem } from '../models/inquiry-cart.models';
import { formatPab } from './format-pab';

export const DEFAULT_WHATSAPP_NUMBER = '50765226428';

export function sanitizeWhatsappNumber(phoneNumber: string | null | undefined): string {
  const digits = (phoneNumber ?? '').replace(/\D+/g, '');
  return digits || DEFAULT_WHATSAPP_NUMBER;
}

export function formatWhatsappDisplayNumber(phoneNumber: string | null | undefined): string {
  const digits = sanitizeWhatsappNumber(phoneNumber);
  if (digits.length === 11 && digits.startsWith('507')) {
    return `+${digits.slice(0, 3)} ${digits.slice(3, 7)}-${digits.slice(7)}`;
  }
  return `+${digits}`;
}

export function calculateInquirySubtotal(items: readonly InquiryCartItem[]): number {
  return items.reduce((sum, item) => {
    if (item.unitPricePab === null || !Number.isFinite(item.unitPricePab)) {
      return sum;
    }
    return sum + item.unitPricePab * item.quantity;
  }, 0);
}

export function buildWhatsappInquiryMessage(items: readonly InquiryCartItem[]): string {
  if (items.length === 0) {
    return 'Hola La Casa del Jean, quisiera consultar disponibilidad de prendas del catálogo.';
  }

  const lines: string[] = [
    'Hola La Casa del Jean, quisiera consultar disponibilidad de las siguientes prendas:',
    '',
  ];

  let hasUnpriced = false;

  for (const item of items) {
    const unitLabel =
      item.unitPricePab !== null && Number.isFinite(item.unitPricePab)
        ? formatPab(item.unitPricePab, item.currency)
        : 'Precio por confirmar';

    let lineSubtotalLabel = 'Por confirmar';
    if (item.unitPricePab !== null && Number.isFinite(item.unitPricePab)) {
      lineSubtotalLabel = formatPab(item.unitPricePab * item.quantity, item.currency);
    } else {
      hasUnpriced = true;
    }

    const details = [
      `SKU: ${item.sku}`,
      `Talla: ${item.size}`,
      item.color ? `Color: ${item.color}` : null,
      `Cantidad: ${item.quantity}`,
      `Precio indicativo: ${unitLabel} c/u (Subtotal: ${lineSubtotalLabel})`,
    ].filter(Boolean);

    lines.push(`- ${item.productName} | ${details.join(' | ')}`);
  }

  const totalUnits = items.reduce((sum, item) => sum + item.quantity, 0);
  const subtotal = calculateInquirySubtotal(items);
  const totalFormatted = formatPab(subtotal, items[0]?.currency || 'PAB');

  lines.push('');
  lines.push(`Total unidades: ${totalUnits}`);
  lines.push(
    hasUnpriced
      ? `Total referencial parcial: ${totalFormatted} (algunos precios por confirmar)`
      : `Total referencial: ${totalFormatted}`
  );
  lines.push('Nota: Esta es una consulta de disponibilidad, sin reserva de stock ni pago en línea.');

  return lines.join('\n');
}

export function buildWhatsappInquiryUrl(
  items: readonly InquiryCartItem[],
  phoneNumber: string | null | undefined = DEFAULT_WHATSAPP_NUMBER
): string {
  const sanitized = sanitizeWhatsappNumber(phoneNumber);
  const message = buildWhatsappInquiryMessage(items);
  return `https://wa.me/${sanitized}?text=${encodeURIComponent(message)}`;
}
