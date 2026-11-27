import { HttpClient } from '@angular/common/http';
import { Inject, Injectable, computed, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, of, tap } from 'rxjs';
import { API_BASE_URL } from '../config/api-config';
import {
  AdminRole,
  AuthUser,
  LoginRequest,
  LoginResponse,
  StoredAdminSession,
} from '../models/admin.models';

export const ADMIN_SESSION_STORAGE_KEY = 'lcdj_admin_session_v1';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly baseUrl: string;
  private readonly sessionSignal = signal<StoredAdminSession | null>(this.readStoredSession());
  readonly sessionExpiredNotice = signal<string | null>(null);

  readonly session = computed(() => this.sessionSignal());
  readonly user = computed<AuthUser | null>(() => this.sessionSignal()?.user ?? null);
  readonly role = computed<AdminRole | null>(() => this.sessionSignal()?.user.role ?? null);
  readonly isAuthenticated = computed<boolean>(() => {
    const current = this.sessionSignal();
    return current !== null && !this.isExpired(current.expires_at);
  });
  readonly canWrite = computed<boolean>(() => {
    const r = this.role();
    return this.isAuthenticated() && (r === 'admin' || r === 'operator');
  });
  readonly isAdmin = computed<boolean>(() => this.isAuthenticated() && this.role() === 'admin');

  constructor(
    private readonly http: HttpClient,
    private readonly router: Router,
    @Inject(API_BASE_URL) apiBaseUrl: string
  ) {
    this.baseUrl = apiBaseUrl;
  }

  getAccessToken(): string | null {
    const current = this.sessionSignal();
    if (!current) {
      return null;
    }
    if (this.isExpired(current.expires_at)) {
      this.clearSession('Tu sesión ha expirado. Inicia sesión nuevamente.');
      return null;
    }
    return current.access_token;
  }

  login(payload: LoginRequest): Observable<LoginResponse> {
    this.sessionExpiredNotice.set(null);
    return this.http.post<LoginResponse>(`${this.baseUrl}/api/v1/auth/login`, payload).pipe(
      tap((response) => {
        this.persistSession({
          access_token: response.access_token,
          expires_at: response.expires_at,
          user: response.user,
        });
      })
    );
  }

  verifySession(): Observable<AuthUser | null> {
    if (!this.getAccessToken()) {
      return of(null);
    }
    return this.http.get<AuthUser>(`${this.baseUrl}/api/v1/auth/me`).pipe(
      tap((user) => {
        const current = this.sessionSignal();
        if (current) {
          this.persistSession({ ...current, user });
        }
      }),
      catchError(() => {
        this.clearSession('Tu sesión ha expirado o fue revocada. Inicia sesión nuevamente.');
        return of(null);
      })
    );
  }

  logout(): Observable<void> {
    const token = this.sessionSignal()?.access_token;
    if (!token) {
      this.clearSession(null);
      return of(void 0);
    }
    return this.http.post<void>(`${this.baseUrl}/api/v1/auth/logout`, {}).pipe(
      catchError(() => of(void 0)),
      finalize(() => {
        this.clearSession(null);
        void this.router.navigate(['/admin/login']);
      })
    );
  }

  handleUnauthorized(message = 'Tu sesión ha expirado. Inicia sesión nuevamente.'): void {
    this.clearSession(message);
    if (!this.router.url.startsWith('/admin/login')) {
      void this.router.navigate(['/admin/login'], {
        queryParams: { returnUrl: this.router.url },
      });
    }
  }

  clearNotice(): void {
    this.sessionExpiredNotice.set(null);
  }

  hasAnyRole(allowed: readonly AdminRole[]): boolean {
    const r = this.role();
    return this.isAuthenticated() && r !== null && allowed.includes(r);
  }

  private isExpired(expiresAt: string): boolean {
    const ts = Date.parse(expiresAt);
    if (Number.isNaN(ts)) {
      return true;
    }
    return ts <= Date.now();
  }

  private persistSession(session: StoredAdminSession): void {
    this.sessionSignal.set(session);
    try {
      sessionStorage.setItem(ADMIN_SESSION_STORAGE_KEY, JSON.stringify(session));
    } catch {
      // Ignore storage quota errors
    }
  }

  private clearSession(notice: string | null): void {
    this.sessionSignal.set(null);
    this.sessionExpiredNotice.set(notice);
    try {
      sessionStorage.removeItem(ADMIN_SESSION_STORAGE_KEY);
    } catch {
      // Ignore storage errors
    }
  }

  private readStoredSession(): StoredAdminSession | null {
    try {
      const raw = sessionStorage.getItem(ADMIN_SESSION_STORAGE_KEY);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw) as Partial<StoredAdminSession>;
      if (
        !parsed ||
        typeof parsed.access_token !== 'string' ||
        typeof parsed.expires_at !== 'string' ||
        !parsed.user ||
        typeof parsed.user.email !== 'string' ||
        typeof parsed.user.role !== 'string'
      ) {
        sessionStorage.removeItem(ADMIN_SESSION_STORAGE_KEY);
        return null;
      }
      if (this.isExpired(parsed.expires_at)) {
        sessionStorage.removeItem(ADMIN_SESSION_STORAGE_KEY);
        return null;
      }
      return parsed as StoredAdminSession;
    } catch {
      return null;
    }
  }
}
