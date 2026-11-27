export function formatPab(
  amount: string | number | null | undefined,
  currency = 'PAB'
): string {
  if (amount === null || amount === undefined || amount === '') {
    return 'Precio por confirmar';
  }
  const numeric = typeof amount === 'number' ? amount : Number(amount);
  if (!Number.isFinite(numeric)) {
    return 'Precio por confirmar';
  }
  const formatted = new Intl.NumberFormat('es-PA', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric);

  const prefix = currency === 'PAB' ? 'B/.' : currency;
  return `${prefix} ${formatted}`;
}

export function getDiscountPercent(
  amount: string | number | null | undefined,
  compareAt: string | number | null | undefined
): number | null {
  const current = Number(amount);
  const original = Number(compareAt);
  if (!Number.isFinite(current) || !Number.isFinite(original) || original <= current || original <= 0) {
    return null;
  }
  return Math.round(((original - current) / original) * 100);
}
