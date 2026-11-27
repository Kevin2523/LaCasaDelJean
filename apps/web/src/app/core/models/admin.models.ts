import { PublicationStatus } from './catalog.models';

export type AdminRole = 'admin' | 'operator' | 'viewer';

export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: AdminRole;
  is_active: boolean;
  last_login_at: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
}

export interface StoredAdminSession {
  access_token: string;
  expires_at: string;
  user: AuthUser;
}

export interface CategoryCreateRequest {
  name: string;
  slug: string;
  description?: string | null;
  parent_id?: string | null;
  display_order?: number;
  is_active?: boolean;
}

export interface CategoryUpdateRequest {
  name?: string;
  slug?: string;
  description?: string | null;
  parent_id?: string | null;
  display_order?: number;
  is_active?: boolean;
}

export interface ProductCreateRequest {
  category_id: string;
  sku: string;
  name: string;
  slug: string;
  description?: string | null;
  publication_status?: PublicationStatus;
}

export interface ProductUpdateRequest {
  category_id?: string;
  sku?: string;
  name?: string;
  slug?: string;
  description?: string | null;
  publication_status?: PublicationStatus;
}

export interface VariantCreateRequest {
  sku: string;
  size: string;
  color: string;
  color_hex?: string | null;
  barcode?: string | null;
  publication_status?: PublicationStatus;
}

export interface VariantUpdateRequest {
  sku?: string;
  size?: string;
  color?: string;
  color_hex?: string | null;
  barcode?: string | null;
  publication_status?: PublicationStatus;
}

export interface PriceCreateRequest {
  variant_id?: string | null;
  amount_pab: string | number;
  compare_at_pab?: string | number | null;
  currency?: 'PAB';
}

export interface ImageUpdateRequest {
  variant_id?: string | null;
  alt_text?: string | null;
  display_order?: number;
  is_primary?: boolean;
}

export type StockDirection = 'in' | 'out' | 'adjustment';

export type StockMovementType =
  | 'initial_load'
  | 'restock'
  | 'manual_adjustment'
  | 'sale_consumption'
  | 'return_in'
  | 'damage_out';

export interface StockMovementCreateRequest {
  variant_id: string;
  direction: StockDirection;
  movement_type: StockMovementType;
  quantity: number;
  idempotency_key?: string | null;
  reference_type?: string | null;
  reference_id?: string | null;
  note?: string | null;
}

export interface StockMovementResult {
  movement_id: string;
  variant_id: string;
  direction: StockDirection;
  movement_type: StockMovementType;
  quantity: number;
  quantity_before: number;
  quantity_after: number;
  idempotency_key: string | null;
  idempotent_replay: boolean;
  created_at: string;
}

export interface StockBalance {
  id: string;
  variant_id: string;
  quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  in_stock: boolean;
  version: number;
  updated_at: string;
}

export interface StockMovement {
  id: string;
  variant_id: string;
  direction: StockDirection;
  movement_type: StockMovementType;
  quantity: number;
  quantity_before: number;
  quantity_after: number;
  idempotency_key: string | null;
  reference_type: string | null;
  reference_id: string | null;
  note: string | null;
  performed_by: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  request_id: string | null;
  created_at: string;
}

export interface AdminCategoryListQuery {
  page?: number;
  page_size?: number;
  search?: string;
  is_active?: boolean;
}

export interface AdminProductListQuery {
  page?: number;
  page_size?: number;
  category_id?: string;
  publication_status?: PublicationStatus;
  search?: string;
}

export interface AuditEventListQuery {
  entity_type?: string;
  action?: string;
  page?: number;
  page_size?: number;
}
