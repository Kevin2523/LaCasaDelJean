import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withInMemoryScrolling } from '@angular/router';
import { routes } from './app.routes';
import { API_BASE_URL, WHATSAPP_NUMBER, resolveApiBaseUrl, resolveWhatsappNumber } from './core/config/api-config';
import { authInterceptor } from './core/interceptors/auth.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(
      routes,
      withInMemoryScrolling({ scrollPositionRestoration: 'enabled' })
    ),
    provideHttpClient(withInterceptors([authInterceptor])),
    {
      provide: API_BASE_URL,
      useFactory: resolveApiBaseUrl,
    },
    {
      provide: WHATSAPP_NUMBER,
      useFactory: resolveWhatsappNumber,
    },
  ],
};
