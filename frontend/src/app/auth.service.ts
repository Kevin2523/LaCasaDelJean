import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { Router } from '@angular/router';

/**
 * AuthService — Gestión centralizada de autenticación
 *
 * ✅ V-06: Valida la sesión contra el servidor, no solo localStorage
 * ✅ V-07: Usa sessionStorage en lugar de localStorage para datos de sesión
 * ✅ V-08: El token/sesión se maneja de forma centralizada aquí
 */
@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  // ⚠️ En producción cambia a tu dominio real
  private readonly baseUrl = 'http://localhost/LaCasaDelJean/backend/';

  /**
   * Realiza el login contra el backend y almacena el estado en sessionStorage.
   * ✅ V-07: sessionStorage (no localStorage) — se borra al cerrar el navegador
   */
  login(correo: string, password: string): Observable<{ success: boolean; nombre?: string; message?: string }> {
    return this.http.post<any>(`${this.baseUrl}login_cliente.php`, { correo, password }, {
      withCredentials: true // ✅ Necesario para que el servidor pueda establecer cookies de sesión
    }).pipe(
      map(res => {
        if (res.status === 'success') {
          const nombreLimpio = (res.nombre ?? '').toString().trim();
          // ✅ V-07: sessionStorage en lugar de localStorage
          sessionStorage.setItem('is_logged', 'true');
          sessionStorage.setItem('user_name', nombreLimpio);
          sessionStorage.setItem('user', JSON.stringify({ nombre: nombreLimpio }));
          return { success: true, nombre: nombreLimpio };
        }
        return { success: false, message: res.message };
      }),
      catchError(() => of({ success: false, message: 'Error de conexión con el servidor' }))
    );
  }

  /**
   * Verifica la sesión activa contra el servidor PHP.
   * ✅ V-06: Validación real, no solo un localStorage bypasseable
   */
  checkSession(): Observable<boolean> {
    return this.http.get<{ valid: boolean; nombre?: string }>(
      `${this.baseUrl}check_session.php`,
      { withCredentials: true }
    ).pipe(
      map(res => {
        if (res.valid) {
          const nombreLimpio = (res.nombre ?? '').toString().trim();
          sessionStorage.setItem('user_name', nombreLimpio);
          sessionStorage.setItem('user', JSON.stringify({ nombre: nombreLimpio }));
        }
        return res.valid;
      }),
      catchError(() => of(false))
    );
  }

  /**
   * Cierra la sesión tanto en el servidor como en el cliente.
   */
  logout(): void {
    this.http.post(`${this.baseUrl}logout.php`, {}, { withCredentials: true }).subscribe();
    // ✅ V-07: Limpiar sessionStorage (no localStorage)
    sessionStorage.clear();
    this.router.navigate(['/']);
  }

  /**
   * Verificación local rápida (solo para UX, no para seguridad).
   * La seguridad real siempre la decide checkSession() contra el servidor.
   */
  isLoggedInLocally(): boolean {
    return sessionStorage.getItem('is_logged') === 'true';
  }

  getUserName(): string {
    return (sessionStorage.getItem('user_name') ?? 'Invitado').toString().trim() || 'Invitado';
  }
}



