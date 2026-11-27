export type PublicationStatus = 'draft' | 'published' | 'archived';

export type ProductSortBy =
  | 'newest'
  | 'name_asc'
  | 'name_desc'
  | 'price_asc'
  | 'price_desc';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id?: string | null;
}

export interface ErrorEnvelope {
  error: ErrorDetail;
}

export interface CategorySummary {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  parent_id: string | null;
  display_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PriceOut {
  id: string;
  product_id: string;
  variant_id: string | null;
  amount_pab: string;
  compare_at_pab: string | null;
  currency: string;
  is_current: boolean;
  valid_from: string;
  valid_to: string | null;
  created_at: string;
}

export interface ImageOut {
  id: string;
  product_id: string;
  variant_id: string | null;
  storage_path: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  width: number;
  height: number;
  sha256: string;
  alt_text: string | null;
  display_order: number;
  is_primary: boolean;
  created_at: string;
}

export interface VariantStockSummary {
  quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  in_stock: boolean;
  version: number;
  updated_at: string;
}

export interface VariantOut {
  id: string;
  product_id: string;
  sku: string;
  size: string;
  color: string;
  color_hex: string | null;
  barcode: string | null;
  publication_status: PublicationStatus;
  current_price: PriceOut | null;
  stock: VariantStockSummary | null;
  created_at: string;
  updated_at: string;
}

export interface ProductListItem {
  id: string;
  category_id: string;
  category_name: string;
  category_slug: string;
  sku: string;
  name: string;
  slug: string;
  description: string | null;
  publication_status: PublicationStatus;
  published_at: string | null;
  current_price: PriceOut | null;
  primary_image: ImageOut | null;
  available_stock: number;
  in_stock: boolean;
  published_variant_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductDetail {
  id: string;
  category_id: string;
  category: CategorySummary;
  sku: string;
  name: string;
  slug: string;
  description: string | null;
  publication_status: PublicationStatus;
  published_at: string | null;
  current_price: PriceOut | null;
  variants: VariantOut[];
  images: ImageOut[];
  created_at: string;
  updated_at: string;
}

export interface CategoryListQuery {
  page?: number;
  page_size?: number;
  parent_id?: string;
  search?: string;
}

export interface ProductListQuery {
  page?: number;
  page_size?: number;
  category_id?: string;
  category_slug?: string;
  search?: string;
  size?: string;
  color?: string;
  in_stock?: boolean;
  min_price_pab?: number | string;
  max_price_pab?: number | string;
  sort_by?: ProductSortBy;
}
