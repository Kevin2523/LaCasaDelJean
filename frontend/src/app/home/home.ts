import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './home.html',
  styleUrl: './home.css'
})
export class HomeComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost/LaCasaDelJean/backend/';

  productosDestacados = signal<any[]>([]);
  configTienda = signal<{ wa_principal: string; wa_plantilla: string }>({
    wa_principal: '',
    wa_plantilla: 'Hola, me interesa [Nombre].'
  });

  ngOnInit() {
    this.http.get<any[]>(`${this.baseUrl}productos_destacados.php`).subscribe({
      next: (data) => {
        const destacados = this.obtenerDestacadoPorCategoria(data ?? []);
        this.productosDestacados.set(destacados);
      },
      error: (err) => console.error('Error obteniendo destacados:', err)
    });

    this.http.get<any>(`${this.baseUrl}config_cliente.php`).subscribe({
      next: (data) => {
        const config = this.extraerConfigWhatsApp(data);
        this.configTienda.set({
          wa_principal: (config?.wa_principal ?? '').toString().trim(),
          wa_plantilla: (config?.wa_plantilla ?? 'Hola, me interesa [Nombre].').toString().trim()
        });
      },
      error: () => {}
    });
  }

  formatearPrecio(valor: unknown): string {
    const numero = Number(valor ?? 0);
    const precio = Number.isNaN(numero) ? 0 : numero;
    return `$${precio.toFixed(2)}`;
  }

  obtenerTallas(producto: any): string[] {
    const tallaRaw = (producto?.talla ?? '').toString().trim();
    if (!tallaRaw) {
      return [];
    }

    return tallaRaw
      .split(',')
      .map((item: string) => item.trim())
      .filter((item: string) => item.length > 0);
  }

  mostrarGenero(producto: any): string {
    const genero = (producto?.genero ?? '').toString().trim();
    return genero || 'Unisex';
  }

  resolverImagen(imagen: unknown): string {
    const valor = (imagen ?? '').toString().trim();
    if (!valor) {
      return '';
    }

    if (valor.startsWith('http://') || valor.startsWith('https://') || valor.startsWith('data:image/')) {
      return valor;
    }

    const mime = this.detectarMimeBase64(valor);
    return `data:${mime};base64,${valor}`;
  }

  consultarPorWhatsApp(producto: any) {
    let telefono = this.soloDigitos(this.configTienda().wa_principal);
    if (!telefono) {
      return;
    }

    const nombreProducto = (producto?.nombre ?? 'este producto').toString().trim();
    const plantilla = this.configTienda().wa_plantilla || 'Hola, me interesa [Nombre].';
    const mensaje = this.personalizarPlantilla(plantilla, nombreProducto);
    const url = `https://wa.me/${telefono}?text=${encodeURIComponent(mensaje)}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  tieneWhatsAppConfig(): boolean {
    return this.soloDigitos(this.configTienda().wa_principal).length > 0;
  }

  private obtenerDestacadoPorCategoria(productos: any[]): any[] {
    const porCategoria = new Map<string, any>();

    for (const producto of productos) {
      const claveCategoria = (producto?.categoria_id ?? producto?.categoria_nombre ?? '').toString();
      if (!claveCategoria) {
        continue;
      }

      const actual = porCategoria.get(claveCategoria);
      if (!actual || this.esMasReciente(producto, actual)) {
        porCategoria.set(claveCategoria, producto);
      }
    }

    return Array.from(porCategoria.values());
  }

  private esMasReciente(a: any, b: any): boolean {
    const fechaA = this.aTimestamp(a?.fecha_creacion ?? a?.created_at);
    const fechaB = this.aTimestamp(b?.fecha_creacion ?? b?.created_at);

    if (fechaA !== fechaB) {
      return fechaA > fechaB;
    }

    return Number(a?.id ?? 0) > Number(b?.id ?? 0);
  }

  private aTimestamp(fecha: unknown): number {
    if (!fecha) {
      return 0;
    }

    const timestamp = new Date(String(fecha)).getTime();
    return Number.isNaN(timestamp) ? 0 : timestamp;
  }

  private detectarMimeBase64(base64: string): string {
    if (base64.startsWith('iVBOR')) {
      return 'image/png';
    }
    if (base64.startsWith('R0lGOD')) {
      return 'image/gif';
    }
    if (base64.startsWith('UklGR')) {
      return 'image/webp';
    }
    return 'image/jpeg';
  }

  private personalizarPlantilla(plantilla: string, nombreProducto: string): string {
    const conNombre = plantilla
      .replace(/\[\s*nombre\s*\]/gi, nombreProducto)
      .replace(/\[\s*producto\s*\]/gi, nombreProducto)
      .replace(/\{\{\s*nombre\s*\}\}/gi, nombreProducto)
      .replace(/\{\{\s*producto\s*\}\}/gi, nombreProducto);

    return conNombre === plantilla ? `${plantilla} ${nombreProducto}`.trim() : conNombre;
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
}



