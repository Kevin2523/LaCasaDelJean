import { InjectionToken } from '@angular/core';
import { environment } from '../../../environments/environment';

declare global {
  interface Window {
    __LCDJ_CONFIG__?: {
      apiBaseUrl?: string;
    };
  }
}

export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL');

export function resolveApiBaseUrl(): string {
  const runtimeUrl =
    typeof window !== 'undefined' ? window.__LCDJ_CONFIG__?.apiBaseUrl : undefined;
  const raw = runtimeUrl ?? environment.apiBaseUrl ?? '';
  return raw.replace(/\/+$/, '');
}
