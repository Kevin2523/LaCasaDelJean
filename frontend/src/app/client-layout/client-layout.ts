import { Component, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-client-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './client-layout.html',
  styleUrl: './client-layout.css'
})
export class ClientLayoutComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost:8000/';

  mostrarLoginModal = signal(false);
  loginCargando = signal(false);
  loginError = signal('');
  configTienda = signal<{ wa_principal: string; wa_plantilla: string }>({
    wa_principal: '',
    wa_plantilla: 'Hola, me gustaria hacer una consulta.'
  });

  loginEmail = '';
  loginPassword = '';

  ngOnInit(): void {
    this.cargarConfigTienda();
  }

  abrirLoginModal() {
    this.loginError.set('');
    this.mostrarLoginModal.set(true);
  }

  cerrarLoginModal() {
    this.mostrarLoginModal.set(false);
    this.loginEmail = '';
    this.loginPassword = '';
    this.loginError.set('');
    this.loginCargando.set(false);
  }

  ingresar() {
    const correo = this.loginEmail.trim();
    const password = this.loginPassword;

    if (!correo || !password) {
      this.loginError.set('Completa correo y contrasena.');
      return;
    }

    this.loginCargando.set(true);
    this.loginError.set('');

    this.http.post<any>(`${this.baseUrl}login_cliente.php`, { correo, password }).subscribe({
      next: (respuesta) => {
        this.loginCargando.set(false);

        if (this.loginExitoso(respuesta)) {
          this.guardarSesionUsuario(respuesta);
          this.cerrarLoginModal();
          this.router.navigate(['/admin']);
          return;
        }

        const mensaje = (respuesta?.message ?? respuesta?.mensaje ?? 'Credenciales invalidas.').toString();
        this.loginError.set(mensaje);
      },
      error: () => {
        this.loginCargando.set(false);
        this.loginError.set('No fue posible iniciar sesion en este momento.');
      }
    });
  }

  abrirWhatsAppTienda() {
    const telefono = this.soloDigitos(this.configTienda().wa_principal);
    if (!telefono) {
      return;
    }

    const url = `https://wa.me/${telefono}?text=Hola,%20tengo%20una%20consulta.`;
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  obtenerEnlaceWhatsAppHeader(): string {
    const telefono = this.soloDigitos(this.configTienda().wa_principal);
    if (!telefono) {
      return '#';
    }

    return `https://wa.me/${telefono}?text=Hola,%20tengo%20una%20consulta.`;
  }

  tieneWhatsAppConfig(): boolean {
    return this.soloDigitos(this.configTienda().wa_principal).length > 0;
  }

  private cargarConfigTienda() {
    this.http.get<any>(`${this.baseUrl}configuracion.php`).subscribe({
      next: (data) => {
        const config = this.extraerConfigWhatsApp(data);
        this.configTienda.set({
          wa_principal: (config?.wa_principal ?? '').toString().trim(),
          wa_plantilla: (config?.wa_plantilla ?? 'Hola, me gustaria hacer una consulta.').toString().trim()
        });
      },
      error: () => {}
    });
  }

  private loginExitoso(respuesta: any): boolean {
    if (!respuesta) {
      return false;
    }

    if (respuesta?.success === true || respuesta?.ok === true || respuesta?.status === 'success') {
      return true;
    }

    if (respuesta?.usuario || respuesta?.user || respuesta?.token) {
      return true;
    }

    return false;
  }

  private soloDigitos(texto: string): string {
    return (texto ?? '').replace(/\D/g, '');
  }

  private extraerConfigWhatsApp(payload: any): any {
    if (!payload) {
      return {};
    }

    return (
      payload?.whatsapp ??
      payload?.config_whatsapp ??
      payload?.data?.whatsapp ??
      payload?.data?.config_whatsapp ??
      payload?.config ??
      payload?.data ??
      payload
    );
  }

  private guardarSesionUsuario(respuesta: any): void {
    if (typeof localStorage === 'undefined') {
      return;
    }

    const nombre = (
      respuesta?.usuario?.nombre ??
      respuesta?.user?.nombre ??
      respuesta?.usuario_nombre ??
      respuesta?.nombre ??
      'Administrador'
    ).toString().trim();

    localStorage.setItem('is_logged', 'true');
    localStorage.setItem('user_name', nombre || 'Administrador');
  }
}
