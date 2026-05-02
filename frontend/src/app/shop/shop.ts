import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-shop',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './shop.html',
  styleUrl: './shop.css'
})
export class ShopComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost/LaCasaDelJean/backend/';

  productosTienda = signal<any[]>([]);
  categorias = signal<any[]>([]);
  configTienda = signal<{ wa_principal: string; wa_plantilla: string }>({
    wa_principal: '',
    wa_plantilla: 'Hola, me interesa [Nombre].'
  });
  generoSeleccionado = signal('Cualquiera');
  categoriasSeleccionadas = signal<number[]>([]);
  textoBusqueda = signal('');
  filtrosMobileAbierto = signal(false);

  productosFiltrados = computed(() => {
    const busqueda = this.textoBusqueda().trim().toLowerCase();
    const genero = this.generoSeleccionado().toLowerCase();
    const categoriasMarcadas = this.categoriasSeleccionadas();
    const filtraCategorias = categoriasMarcadas.length > 0;
    const categoriasActivas = this.categorias()
      .filter((cat) => categoriasMarcadas.includes(Number(cat?.id ?? 0)))
      .map((cat) => (cat?.nombre ?? '').toString().trim().toLowerCase());

    return this.productosTienda().filter((producto) => {
      const generoProducto = (producto?.genero ?? '').toString().trim().toLowerCase();
      const categoriaId = Number(producto?.categoria_id ?? 0);
      const categoriaNombre = (producto?.categoria_nombre ?? '').toString().trim().toLowerCase();
      const nombre = (producto?.nombre ?? '').toString().trim().toLowerCase();
      const talla = (producto?.talla ?? '').toString().trim().toLowerCase();

      const coincideGenero = genero === 'cualquiera' || generoProducto === genero;
      const coincideCategoria =
        !filtraCategorias ||
        categoriasMarcadas.includes(categoriaId) ||
        categoriasActivas.includes(categoriaNombre);
      const coincideBusqueda =
        !busqueda ||
        nombre.includes(busqueda) ||
        categoriaNombre.includes(busqueda) ||
        generoProducto.includes(busqueda) ||
        talla.includes(busqueda);

      return coincideGenero && coincideCategoria && coincideBusqueda;
    });
  });

  ngOnInit() {
    this.cargarProductos();
    this.cargarCategorias();
    this.cargarConfigTienda();
  }

  cargarProductos() {
    this.http.get<any>(`${this.baseUrl}productos_cliente.php`).subscribe({
      next: (data) => {
        const productos = this.extraerLista(data);
        this.productosTienda.set(productos);
      },
      error: (err) => console.error('Error obteniendo productos tienda:', err)
    });
  }

  cargarCategorias() {
    this.http.get<any>(`${this.baseUrl}categorias.php`).subscribe({
      next: (data) => this.categorias.set(this.extraerLista(data)),
      error: (err) => console.error('Error obteniendo categorías:', err)
    });
  }

  cargarConfigTienda() {
    this.http.get<any>(`${this.baseUrl}config_cliente.php`).subscribe({
      next: (data) => {
        const config = this.extraerConfigWhatsApp(data);
        this.configTienda.set({
          wa_principal: (config?.wa_principal ?? '').toString().trim(),
          wa_plantilla: (config?.wa_plantilla ?? 'Hola, me interesa [Nombre].').toString().trim()
        });
      },
      error: (err) => console.error('Error obteniendo config de tienda:', err)
    });
  }

  toggleCategoria(categoriaId: number, checked: boolean) {
    const actuales = this.categoriasSeleccionadas();

    if (checked && !actuales.includes(categoriaId)) {
      this.categoriasSeleccionadas.set([...actuales, categoriaId]);
      return;
    }

    if (!checked) {
      this.categoriasSeleccionadas.set(actuales.filter((id) => id !== categoriaId));
    }
  }

  cambiarGenero(event: Event) {
    const select = event.target as HTMLSelectElement;
    this.generoSeleccionado.set(select?.value ?? 'Cualquiera');
  }

  limpiarCategorias() {
    this.categoriasSeleccionadas.set([]);
  }

  actualizarBusqueda(event: Event) {
    const input = event.target as HTMLInputElement;
    this.textoBusqueda.set(input?.value ?? '');
  }

  mostrarGenero(producto: any): string {
    const genero = (producto?.genero ?? '').toString().trim();
    return genero || 'Unisex';
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

  formatearPrecio(valor: unknown): string {
    const numero = Number(valor ?? 0);
    const precio = Number.isNaN(numero) ? 0 : numero;
    return `$${precio.toFixed(2)}`;
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

  private extraerLista(payload: any): any[] {
    if (Array.isArray(payload)) {
      return payload;
    }

    if (Array.isArray(payload?.data)) {
      return payload.data;
    }

    if (Array.isArray(payload?.productos)) {
      return payload.productos;
    }

    if (Array.isArray(payload?.categorias)) {
      return payload.categorias;
    }

    return [];
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



