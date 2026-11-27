import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../config/api-config';
import {
  AdminCategoryListQuery,
  AdminProductListQuery,
  AuditEvent,
  AuditEventListQuery,
  CategoryCreateRequest,
  CategoryUpdateRequest,
  ImageUpdateRequest,
  PriceCreateRequest,
  ProductCreateRequest,
  ProductUpdateRequest,
  StockBalance,
  StockMovement,
  StockMovementCreateRequest,
  StockMovementResult,
  VariantCreateRequest,
  VariantUpdateRequest,
} from '../models/admin.models';
import {
  CategorySummary,
  ErrorEnvelope,
  ImageOut,
  PaginatedResponse,
  PriceOut,
  ProductDetail,
  ProductListItem,
  VariantOut,
} from '../models/catalog.models';

@Injectable({ providedIn: 'root' })
export class AdminApiService {
  private readonly baseUrl: string;

  constructor(
    private readonly http: HttpClient,
    @Inject(API_BASE_URL) apiBaseUrl: string
  ) {
    this.baseUrl = apiBaseUrl;
  }

  // Categories
  listCategories(
    query: AdminCategoryListQuery = {}
  ): Observable<PaginatedResponse<CategorySummary>> {
    let params = new HttpParams();
    if (query.page !== undefined) params = params.set('page', String(query.page));
    if (query.page_size !== undefined) params = params.set('page_size', String(query.page_size));
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    if (query.is_active !== undefined) params = params.set('is_active', String(query.is_active));
    return this.http.get<PaginatedResponse<CategorySummary>>(
      `${this.baseUrl}/api/v1/admin/categories`,
      { params }
    );
  }

  createCategory(payload: CategoryCreateRequest): Observable<CategorySummary> {
    return this.http.post<CategorySummary>(`${this.baseUrl}/api/v1/admin/categories`, payload);
  }

  updateCategory(categoryId: string, payload: CategoryUpdateRequest): Observable<CategorySummary> {
    return this.http.patch<CategorySummary>(
      `${this.baseUrl}/api/v1/admin/categories/${encodeURIComponent(categoryId)}`,
      payload
    );
  }

  // Products
  listProducts(query: AdminProductListQuery = {}): Observable<PaginatedResponse<ProductListItem>> {
    let params = new HttpParams();
    if (query.page !== undefined) params = params.set('page', String(query.page));
    if (query.page_size !== undefined) params = params.set('page_size', String(query.page_size));
    if (query.category_id) params = params.set('category_id', query.category_id);
    if (query.publication_status) {
      params = params.set('publication_status', query.publication_status);
    }
    if (query.search?.trim()) params = params.set('search', query.search.trim());
    return this.http.get<PaginatedResponse<ProductListItem>>(
      `${this.baseUrl}/api/v1/admin/products`,
      { params }
    );
  }

  getProduct(productId: string): Observable<ProductDetail> {
    return this.http.get<ProductDetail>(
      `${this.baseUrl}/api/v1/admin/products/${encodeURIComponent(productId)}`
    );
  }

  createProduct(payload: ProductCreateRequest): Observable<ProductDetail> {
    return this.http.post<ProductDetail>(`${this.baseUrl}/api/v1/admin/products`, payload);
  }

  updateProduct(productId: string, payload: ProductUpdateRequest): Observable<ProductDetail> {
    return this.http.patch<ProductDetail>(
      `${this.baseUrl}/api/v1/admin/products/${encodeURIComponent(productId)}`,
      payload
    );
  }

  // Variants
  createVariant(productId: string, payload: VariantCreateRequest): Observable<VariantOut> {
    return this.http.post<VariantOut>(
      `${this.baseUrl}/api/v1/admin/products/${encodeURIComponent(productId)}/variants`,
      payload
    );
  }

  updateVariant(variantId: string, payload: VariantUpdateRequest): Observable<VariantOut> {
    return this.http.patch<VariantOut>(
      `${this.baseUrl}/api/v1/admin/variants/${encodeURIComponent(variantId)}`,
      payload
    );
  }

  // Prices (PAB)
  setCurrentPrice(productId: string, payload: PriceCreateRequest): Observable<PriceOut> {
    return this.http.post<PriceOut>(
      `${this.baseUrl}/api/v1/admin/products/${encodeURIComponent(productId)}/prices`,
      { ...payload, currency: 'PAB' }
    );
  }

  // Images
  uploadProductImage(
    productId: string,
    file: File,
    options: {
      variant_id?: string | null;
      alt_text?: string | null;
      display_order?: number;
      is_primary?: boolean;
    } = {}
  ): Observable<ImageOut> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    if (options.variant_id) formData.append('variant_id', options.variant_id);
    if (options.alt_text?.trim()) formData.append('alt_text', options.alt_text.trim());
    if (options.display_order !== undefined) {
      formData.append('display_order', String(options.display_order));
    }
    if (options.is_primary !== undefined) {
      formData.append('is_primary', String(options.is_primary));
    }

    return this.http.post<ImageOut>(
      `${this.baseUrl}/api/v1/admin/products/${encodeURIComponent(productId)}/images/upload`,
      formData
    );
  }

  updateImageMetadata(imageId: string, payload: ImageUpdateRequest): Observable<ImageOut> {
    return this.http.patch<ImageOut>(
      `${this.baseUrl}/api/v1/admin/images/${encodeURIComponent(imageId)}`,
      payload
    );
  }

  deleteImageMetadata(imageId: string): Observable<void> {
    return this.http.delete<void>(
      `${this.baseUrl}/api/v1/admin/images/${encodeURIComponent(imageId)}`
    );
  }

  // Inventory
  getVariantBalance(variantId: string): Observable<StockBalance> {
    return this.http.get<StockBalance>(
      `${this.baseUrl}/api/v1/inventory/variants/${encodeURIComponent(variantId)}/balance`
    );
  }

  listVariantMovements(
    variantId: string,
    page = 1,
    pageSize = 20
  ): Observable<PaginatedResponse<StockMovement>> {
    const params = new HttpParams().set('page', String(page)).set('page_size', String(pageSize));
    return this.http.get<PaginatedResponse<StockMovement>>(
      `${this.baseUrl}/api/v1/inventory/variants/${encodeURIComponent(variantId)}/movements`,
      { params }
    );
  }

  createStockMovement(payload: StockMovementCreateRequest): Observable<StockMovementResult> {
    return this.http.post<StockMovementResult>(`${this.baseUrl}/api/v1/inventory/movements`, payload);
  }

  // Audit (admin role only)
  listAuditEvents(query: AuditEventListQuery = {}): Observable<PaginatedResponse<AuditEvent>> {
    let params = new HttpParams();
    if (query.entity_type) params = params.set('entity_type', query.entity_type);
    if (query.action) params = params.set('action', query.action);
    if (query.page !== undefined) params = params.set('page', String(query.page));
    if (query.page_size !== undefined) params = params.set('page_size', String(query.page_size));
    return this.http.get<PaginatedResponse<AuditEvent>>(
      `${this.baseUrl}/api/v1/admin/audit-events`,
      { params }
    );
  }

  extractErrorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 0) {
        return 'No se pudo conectar con la API. Verifica que el servidor FastAPI esté activo.';
      }
      const envelope = error.error as Partial<ErrorEnvelope> | null;
      if (envelope?.error?.message) {
        return envelope.error.message;
      }
      if (error.status === 401) {
        return 'Credenciales inválidas o sesión expirada.';
      }
      if (error.status === 403) {
        return 'No tienes permisos suficientes para realizar esta operación.';
      }
      if (error.status === 404) {
        return 'El recurso solicitado no existe.';
      }
      if (error.status === 409) {
        return 'Conflicto de datos (posible SKU, slug duplicado o stock insuficiente).';
      }
      if (error.status === 422) {
        return 'Los datos enviados no cumplen las validaciones requeridas.';
      }
      return `Error del servidor (HTTP ${error.status}).`;
    }
    return 'Ocurrió un error inesperado.';
  }
}
