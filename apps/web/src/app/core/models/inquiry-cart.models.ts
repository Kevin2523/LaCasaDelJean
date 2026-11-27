export const INQUIRY_CART_STORAGE_KEY = 'lcdj_inquiry_cart_v1';
export const INQUIRY_CART_STORAGE_VERSION = 1;
export const INQUIRY_CART_MAX_QUANTITY = 99;

export interface InquiryCartItem {
  /** Unique key combining productId and variantId (or 'default' if no variant). */
  key: string;
  productId: string;
  productSlug: string;
  productName: string;
  categorySlug: string;
  sku: string;
  variantId: string | null;
  size: string;
  color: string;
  /** Indicative unit price in PAB (null if price is pending confirmation). */
  unitPricePab: number | null;
  currency: string;
  quantity: number;
  imageUrl: string;
  imageAlt: string;
}

export interface InquiryCartStoragePayload {
  version: number;
  updatedAt: string;
  items: InquiryCartItem[];
}
