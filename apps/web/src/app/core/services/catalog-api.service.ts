import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../config/api-config';
import {
  CategoryListQuery,
  CategorySummary,
  ErrorEnvelope,
  PaginatedResponse,
  ProductDetail,
  ProductListItem,
  ProductListQuery,
} from '../models/catalog.models';

@Injectable({ providedIn: 'root' })
export class CatalogApiService {
  private readonly baseUrl: string;

  constructor(
    private readonly http: HttpClient,
    @Inject(API_BASE_URL) apiBaseUrl: string
  ) {
    this.baseUrl = apiBaseUrl;
  }

  listCategories(
    query: CategoryListQuery = {}
  ): Observable<PaginatedResponse<CategorySummary>> {
    let params = new HttpParams();
    if (query.page !== undefined) {
      params = params.set('page', String(query.page));
    }
    if (query.page_size !== undefined) {
      params = params.set('page_size', String(query.page_size));
    }
    if (query.parent_id) {
      params = params.set('parent_id', query.parent_id);
    }
    if (query.search?.trim()) {
      params = params.set('search', query.search.trim());
    }

    return this.http.get<PaginatedResponse<CategorySummary>>(
      `${this.baseUrl}/api/v1/categories`,
      { params }
    );
  }

  getCategoryBySlug(slug: string): Observable<CategorySummary> {
    return this.http.get<CategorySummary>(
      `${this.baseUrl}/api/v1/categories/slug/${encodeURIComponent(slug)}`
    );
  }

  listProducts(
    query: ProductListQuery = {}
  ): Observable<PaginatedResponse<ProductListItem>> {
    let params = new HttpParams();
    if (query.page !== undefined) {
      params = params.set('page', String(query.page));
    }
    if (query.page_size !== undefined) {
      params = params.set('page_size', String(query.page_size));
    }
    if (query.category_id) {
      params = params.set('category_id', query.category_id);
    }
    if (query.category_slug?.trim()) {
      params = params.set('category_slug', query.category_slug.trim());
    }
    if (query.search?.trim()) {
      params = params.set('search', query.search.trim());
    }
    if (query.size?.trim()) {
      params = params.set('size', query.size.trim());
    }
    if (query.color?.trim()) {
      params = params.set('color', query.color.trim());
    }
    if (query.in_stock !== undefined) {
      params = params.set('in_stock', String(query.in_stock));
    }
    if (
      query.min_price_pab !== undefined &&
      query.min_price_pab !== null &&
      String(query.min_price_pab).trim() !== ''
    ) {
      params = params.set('min_price_pab', String(query.min_price_pab));
    }
    if (
      query.max_price_pab !== undefined &&
      query.max_price_pab !== null &&
      String(query.max_price_pab).trim() !== ''
    ) {
      params = params.set('max_price_pab', String(query.max_price_pab));
    }
    if (query.sort_by) {
      params = params.set('sort_by', query.sort_by);
    }

    return this.http.get<PaginatedResponse<ProductListItem>>(
      `${this.baseUrl}/api/v1/products`,
      { params }
    );
  }

  getProductBySlug(slug: string): Observable<ProductDetail> {
    return this.http.get<ProductDetail>(
      `${this.baseUrl}/api/v1/products/slug/${encodeURIComponent(slug)}`
    );
  }

  getProductById(productId: string): Observable<ProductDetail> {
    return this.http.get<ProductDetail>(
      `${this.baseUrl}/api/v1/products/${encodeURIComponent(productId)}`
    );
  }

  extractErrorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 0) {
        return 'No pudimos conectar con el catálogo. Verifica tu conexión o intenta de nuevo en unos momentos.';
      }
      const envelope = error.error as Partial<ErrorEnvelope> | null;
      if (envelope?.error?.message) {
        return envelope.error.message;
      }
      if (error.status === 404) {
        return 'El recurso solicitado no se encuentra disponible en el catálogo.';
      }
      return `Ocurrió un error al consultar el catálogo (HTTP ${error.status}).`;
    }
    return 'Ocurrió un error inesperado al cargar la información.';
  }
}
