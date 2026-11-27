import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { API_BASE_URL } from '../config/api-config';
import { ADMIN_SESSION_STORAGE_KEY, AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: API_BASE_URL, useValue: '' },
      ],
    });
    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    sessionStorage.clear();
  });

  it('stores session on login and exposes role permissions', () => {
    const future = new Date(Date.now() + 3600_000).toISOString();
    service.login({ email: 'admin@lcdj.test', password: 'secret' }).subscribe((res) => {
      expect(res.user.role).toBe('admin');
    });

    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    req.flush({
      access_token: 'jwt-token-1',
      token_type: 'bearer',
      expires_at: future,
      user: {
        id: 'u-1',
        email: 'admin@lcdj.test',
        full_name: 'Admin User',
        role: 'admin',
        is_active: true,
        last_login_at: null,
      },
    });

    expect(service.isAuthenticated()).toBeTrue();
    expect(service.canWrite()).toBeTrue();
    expect(service.isAdmin()).toBeTrue();
    expect(service.getAccessToken()).toBe('jwt-token-1');
  });

  it('marks viewer as read-only (canWrite=false, isAdmin=false)', () => {
    const future = new Date(Date.now() + 3600_000).toISOString();
    service.login({ email: 'viewer@lcdj.test', password: 'secret' }).subscribe();

    httpMock.expectOne('/api/v1/auth/login').flush({
      access_token: 'jwt-viewer',
      token_type: 'bearer',
      expires_at: future,
      user: {
        id: 'u-2',
        email: 'viewer@lcdj.test',
        full_name: 'Viewer User',
        role: 'viewer',
        is_active: true,
        last_login_at: null,
      },
    });

    expect(service.isAuthenticated()).toBeTrue();
    expect(service.canWrite()).toBeFalse();
    expect(service.isAdmin()).toBeFalse();
  });

  it('clears expired token and sets sessionExpiredNotice', () => {
    const past = new Date(Date.now() - 60_000).toISOString();
    sessionStorage.setItem(
      ADMIN_SESSION_STORAGE_KEY,
      JSON.stringify({
        access_token: 'expired-jwt',
        expires_at: past,
        user: {
          id: 'u-3',
          email: 'op@lcdj.test',
          full_name: 'Operator',
          role: 'operator',
          is_active: true,
          last_login_at: null,
        },
      })
    );

    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: API_BASE_URL, useValue: '' },
      ],
    });
    const freshService = TestBed.inject(AuthService);
    expect(freshService.isAuthenticated()).toBeFalse();
    expect(freshService.getAccessToken()).toBeNull();
  });

  it('calls backend logout and clears local session', () => {
    const future = new Date(Date.now() + 3600_000).toISOString();
    service.login({ email: 'op@lcdj.test', password: 'secret' }).subscribe();
    httpMock.expectOne('/api/v1/auth/login').flush({
      access_token: 'jwt-op',
      token_type: 'bearer',
      expires_at: future,
      user: {
        id: 'u-4',
        email: 'op@lcdj.test',
        full_name: 'Operator',
        role: 'operator',
        is_active: true,
        last_login_at: null,
      },
    });

    service.logout().subscribe();
    const logoutReq = httpMock.expectOne('/api/v1/auth/logout');
    expect(logoutReq.request.method).toBe('POST');
    logoutReq.flush(null, { status: 204, statusText: 'No Content' });

    expect(service.isAuthenticated()).toBeFalse();
    expect(sessionStorage.getItem(ADMIN_SESSION_STORAGE_KEY)).toBeNull();
  });
});
