import { InjectionToken } from '@angular/core';
import { environment } from '../../../environments/environment';
import { DEFAULT_WHATSAPP_NUMBER, sanitizeWhatsappNumber } from '../utils/whatsapp-link';

declare global {
  interface Window {
    __LCDJ_CONFIG__?: {
      apiBaseUrl?: string;
      whatsappNumber?: string;
    };
  }
}

export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL');
export const WHATSAPP_NUMBER = new InjectionToken<string>('WHATSAPP_NUMBER', {
  providedIn: 'root',
  factory: resolveWhatsappNumber,
});

export function resolveApiBaseUrl(): string {
  const runtimeUrl =
    typeof window !== 'undefined' ? window.__LCDJ_CONFIG__?.apiBaseUrl : undefined;
  const raw = runtimeUrl ?? environment.apiBaseUrl ?? '';
  return raw.replace(/\/+$/, '');
}

export function resolveWhatsappNumber(): string {
  const runtimeNumber =
    typeof window !== 'undefined' ? window.__LCDJ_CONFIG__?.whatsappNumber : undefined;
  return sanitizeWhatsappNumber(runtimeNumber ?? environment.whatsappNumber ?? DEFAULT_WHATSAPP_NUMBER);
}
