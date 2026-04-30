import { Component, computed, effect, inject, OnInit, signal, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from './api.service';
import { AuthService } from '../auth.service'; // ✅ V-07/V-04: Centralizar auth
import Swal from 'sweetalert2';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin.html',
  styleUrls: ['./admin.css']
})
export class AdminComponent implements OnInit {
  currentView = signal<'dashboard' | 'productos' | 'categorias' | 'contabilidad' | 'configuracion'>('dashboard');

  private readonly apiService = inject(ApiService);
  private readonly router = inject(Router);
  private readonly authService = inject(AuthService); // ✅ V-07

  dashboardData = signal<any>(null);
  productosData = signal<any[]>([]);
  categoriasData = signal<any[]>([]);
  reporteContable = signal<any[]>([]);
  configData = signal<any>(null);
  usuarioLogueado = signal<any>({ nombre: 'Administrador', id: 1 });
  userName = signal('Invitado');
  userInitial = computed(() => (this.userName().trim().charAt(0) || 'I').toUpperCase());
  configWhatsApp = signal<any>({ wa_principal: '', wa_secundario: '', wa_plantilla: '' });
  sidebarAbierta = signal(true);
  tallasParaInventario = signal<{ talla: string; stock: number }[]>([]);
  nuevaPassword = '';

  mostrarModal = signal(false);
  mostrarModalCat = signal(false);
  productoActual = signal<any>({});
  categoriaActual = signal<any>({ nombre: '' });
  filtroCategoria = signal<string>('Todas');
  textoBusqueda = signal('');
  pagoMunicipioForm = signal<{ monto: number; mes: number; anio: number }>({
    monto: 0,
    mes: new Date().getMonth() + 1,
    anio: new Date().getFullYear()
  });

  ultimosAgregadosFiltrados = computed(() => {
    const busqueda = this.textoBusqueda().toLowerCase().trim();
    const agregados = this.dashboardData()?.ultimos_agregados ?? [];
    if (!busqueda) return agregados;
    return agregados.filter((item: any) => (item?.nombre ?? '').toLowerCase().includes(busqueda));
  });

  productosFiltrados = computed(() => {
    const filtro = this.filtroCategoria();
    const busqueda = this.textoBusqueda().toLowerCase().trim();
    const productos = this.productosData();
    return productos.filter((producto: any) => {
      const coincideCategoria = filtro === 'Todas' || producto.categoria_nombre === filtro;
      const coincideBusqueda = (producto?.nombre ?? '').toLowerCase().includes(busqueda);
      return coincideCategoria && coincideBusqueda;
    });
  });

  categoriasFiltradas = computed(() => {
    const busqueda = this.textoBusqueda().toLowerCase().trim();
    const categorias = this.categoriasData();
    if (!busqueda) return categorias;
    return categorias.filter((categoria: any) => (categoria?.nombre ?? '').toLowerCase().includes(busqueda));
  });

  reporteContableResumen = computed(() => {
    const data = this.reporteContable() ?? [];
    return data.map((item: any) => {
      const ventasTotales = Number(item?.ventas_totales ?? item?.utilidad_bruta ?? 0);
      const inversionTotal = Number(item?.inversion_total ?? 0);
      const gastoMunicipal = Number(item?.total_municipio ?? item?.gasto_municipal ?? 0);
      const gananciaReal = Number(item?.ganancia_real ?? (ventasTotales - inversionTotal - gastoMunicipal));

      return {
        mes_nombre: item?.mes_nombre ?? '',
        anio: item?.anio ?? '',
        ventas_totales: ventasTotales,
        inversion_total: inversionTotal,
        gasto_municipal: gastoMunicipal,
        ganancia_real: gananciaReal
      };
    });
  });

  ngOnInit() {
    this.cargarUsuarioDesdeSesion();
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      this.sidebarAbierta.set(false);
    }
    this.cargarDashboard();
    this.obtenerProductos(); // Usamos el nombre consistente
    this.obtenerCategorias();
    this.cargarContabilidad();
    this.cargarConfiguracion();
  }

  toggleSidebar() {
    this.sidebarAbierta.set(!this.sidebarAbierta());
  }

  changeView(view: 'dashboard' | 'productos' | 'categorias' | 'contabilidad' | 'configuracion') {
    this.currentView.set(view);
    if (typeof window !== 'undefined' && window.innerWidth <= 768) {
      this.sidebarAbierta.set(false);
    }
  }

  actualizarBusqueda(event: any) {
    this.textoBusqueda.set((event?.target?.value ?? '').toLowerCase());
  }

  cargarDashboard() {
    this.apiService.getDashboard().subscribe({
      next: (data: any) => this.dashboardData.set(data),
      error: (error: any) => console.error('Error al cargar dashboard:', error)
    });
  }

  obtenerProductos() {
    this.apiService.getProductos().subscribe({
      next: (data: any) => this.productosData.set(data ?? []),
      error: (error: any) => console.error('Error al cargar productos:', error)
    });
  }

  // Alias para mantener compatibilidad con tus llamadas previas
  cargarProductos() {
    this.obtenerProductos();
  }

  obtenerCategorias() {
    this.apiService.getCategorias().subscribe({
      next: (data: any) => this.categoriasData.set(data),
      error: (error: any) => console.error('Error al cargar categorías:', error)
    });
  }

  cargarConfiguracion() {
    this.apiService.getConfiguracion().subscribe({
      next: (data: any) => {
        this.configData.set(data);

        const usuarioData = data?.usuario ?? {};
        const nombreUsuario = (usuarioData?.nombre ?? '').toString().trim();
        // ✅ V-07: sessionStorage en lugar de localStorage
        const nombreSesion = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('user_name') ?? '' : '';
        this.usuarioLogueado.set({
          id: Number(usuarioData?.id ?? data?.usuario_id ?? this.usuarioLogueado().id ?? 1),
          nombre: nombreSesion.trim() || nombreUsuario || 'Invitado'
        });
        this.userName.set((nombreSesion.trim() || nombreUsuario || 'Invitado').trim());

        const whatsappData = data?.whatsapp ?? data?.config_whatsapp ?? data ?? {};
        this.configWhatsApp.set({
          wa_principal: (whatsappData?.wa_principal ?? whatsappData?.telefono_principal ?? '').toString(),
          wa_secundario: (whatsappData?.wa_secundario ?? whatsappData?.telefono_secundario ?? '').toString(),
          wa_plantilla: (whatsappData?.wa_plantilla ?? whatsappData?.mensaje_whatsapp ?? '').toString()
        });
      },
      error: (error: any) => console.error('Error al cargar configuración:', error)
    });
  }

  get waPrincipal(): string {
    return this.configWhatsApp().wa_principal ?? '';
  }

  set waPrincipal(valor: string) {
    this.configWhatsApp.set({ ...this.configWhatsApp(), wa_principal: valor ?? '' });
  }

  get waSecundario(): string {
    return this.configWhatsApp().wa_secundario ?? '';
  }

  set waSecundario(valor: string) {
    this.configWhatsApp.set({ ...this.configWhatsApp(), wa_secundario: valor ?? '' });
  }

  get waPlantilla(): string {
    return this.configWhatsApp().wa_plantilla ?? '';
  }

  set waPlantilla(valor: string) {
    this.configWhatsApp.set({ ...this.configWhatsApp(), wa_plantilla: valor ?? '' });
  }

  guardarWhatsApp() {
    const payload = {
      tipo: 'whatsapp',
      wa_principal: (this.configWhatsApp().wa_principal ?? '').toString().trim(),
      wa_secundario: (this.configWhatsApp().wa_secundario ?? '').toString().trim(),
      wa_plantilla: (this.configWhatsApp().wa_plantilla ?? '').toString().trim()
    };

    this.apiService.guardarConfiguracion(payload).subscribe({
      next: (res: any) => {
        if (res && (res.error || res.success === false)) {
          Swal.fire({ icon: 'warning', title: 'No se pudo guardar', text: res?.message ?? 'Revisa los datos e inténtalo de nuevo.' });
          return;
        }
        Swal.fire({ icon: 'success', title: 'Configuración guardada', text: 'Datos de WhatsApp actualizados correctamente.' });
        this.cargarConfiguracion();
      },
      error: () => Swal.fire({ icon: 'error', title: 'Error', text: 'No fue posible guardar la configuración de WhatsApp.' })
    });
  }

  actualizarPerfil() {
    const password = (this.nuevaPassword ?? '').toString().trim();
    if (!password) {
      Swal.fire({ icon: 'warning', title: 'Contraseña vacía', text: 'Escribe una nueva contraseña para continuar.' });
      return;
    }

    const payload = {
      tipo: 'perfil',
      usuario_id: Number(this.usuarioLogueado()?.id ?? 1),
      nueva_password: password
    };

    this.apiService.guardarConfiguracion(payload).subscribe({
      next: (res: any) => {
        if (res && (res.error || res.success === false)) {
          Swal.fire({ icon: 'warning', title: 'No se pudo actualizar', text: res?.message ?? 'Inténtalo nuevamente.' });
          return;
        }
        this.nuevaPassword = '';
        Swal.fire({ icon: 'success', title: 'Perfil actualizado', text: 'Tu contraseña fue actualizada correctamente.' });
      },
      error: () => Swal.fire({ icon: 'error', title: 'Error', text: 'No fue posible actualizar el perfil.' })
    });
  }

  cargarContabilidad() {
    this.apiService.getContabilidad().subscribe({
      next: (data: any) => this.reporteContable.set(data ?? []),
      error: (error: any) => console.error('Error al cargar contabilidad:', error)
    });
  }

  actualizarPagoMunicipioCampo(campo: 'monto' | 'mes' | 'anio', valor: any) {
    const numero = Number(valor);
    this.pagoMunicipioForm.set({
      ...this.pagoMunicipioForm(),
      [campo]: Number.isNaN(numero) ? 0 : numero
    });
  }

  registrarPago(monto: number, mes: number, anio: number) {
    if (!monto || monto <= 0 || !mes || !anio) {
      Swal.fire({ icon: 'warning', title: 'Datos incompletos', text: 'Ingresa un monto válido, mes y año.', confirmButtonColor: '#d97706' });
      return;
    }
    this.apiService.registrarPagoMunicipio({ monto, mes, anio }).subscribe({
      next: (res: any) => {
        if (res && (res.error || res.success === false)) {
          Swal.fire({ icon: 'warning', title: 'No se pudo registrar', text: res?.message || 'Error en el servidor.', confirmButtonColor: '#d97706' });
          return;
        }
        Swal.fire({ icon: 'success', title: 'Pago registrado', text: 'Guardado correctamente.', confirmButtonColor: '#1e3a8a' });
        this.cargarContabilidad();
      }
    });
  }

  abrirModalNuevo() {
    this.productoActual.set({
      nombre: '',
      genero: 'Unisex',
      talla: '',
      stock: 0,
      precio: 0,
      precio_costo: 0,
      categoria_id: this.categoriasData()[0]?.id ?? null,
      imagen: ''
    });
    this.mostrarModal.set(true);
  }

  abrirModalEditar(prod: any) {
    this.productoActual.set({
      ...prod,
      id: Number(prod.id), // Aseguramos que el ID sea numérico
      talla: (prod?.talla ?? '').toString(),
      stock: Number(prod?.stock ?? 0),
      precio_costo: Number(prod.precio_costo ?? 0),
      categoria_id: prod.categoria_id ?? null
    });
    this.mostrarModal.set(true);
  }

  cerrarModal() {
    this.mostrarModal.set(false);
    this.productoActual.set({});
  }

  actualizarProductoCampo(campo: string, valor: any) {
    const siguiente = {
      ...this.productoActual(),
      [campo]: valor
    };

    this.productoActual.set(siguiente);

    if (campo === 'categoria_id' || campo === 'genero') {
      this.sincronizarTallasConReglas();
    }
  }

  obtenerListaTallas(): string[] {
    const producto = this.productoActual();
    const genero = (producto?.genero ?? '').toString().toLowerCase();
    const categoriaId = Number(producto?.categoria_id ?? 0);
    const categoria = this.categoriasData().find((cat: any) => Number(cat.id) === categoriaId);
    const nombreCategoria = this.normalizarTexto((categoria?.nombre ?? '').toString());

    if (this.esCategoriaSinTallas(nombreCategoria)) {
      return [];
    }

    if (nombreCategoria.includes('pantalon')) {
      if (genero === 'hombre') {
        return ['28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40'];
      }
      if (genero === 'mujer') {
        return ['3-4', '5-6', '7-8', '9-10', '11-12', '13-14', '15-16', '17-18', '19-20', '21-22'];
      }
      return [];
    }

    if (nombreCategoria.includes('zapatilla') || nombreCategoria.includes('zapato') || nombreCategoria.includes('chancleta')) {
      return ['25', '26', '27', '28', '29', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '41', '42', '43', '44', '45'];
    }

    if (nombreCategoria.includes('sueter') || nombreCategoria.includes('blusa') || nombreCategoria.includes('camisa')) {
      return ['S', 'M', 'L', 'XL', 'XXL', 'XXXL'];
    }

    return [];
  }

  obtenerTallasSeleccionadas(): string[] {
    const actual = (this.productoActual()?.talla ?? '').toString();
    return actual.split(',').map((item: string) => item.trim()).filter((item: string) => item.length > 0);
  }

  actualizarSeleccionTalla(talla: string, checked: boolean): void {
    const actuales = this.obtenerTallasSeleccionadas();
    const siguiente = checked
      ? (actuales.includes(talla) ? actuales : [...actuales, talla])
      : actuales.filter((item) => item !== talla);

    this.actualizarProductoCampo('talla', siguiente.join(', '));
  }

  toggleTalla(talla: string): void {
    const actuales = this.obtenerTallasSeleccionadas();
    const siguiente = actuales.includes(talla)
      ? actuales.filter((item) => item !== talla)
      : [...actuales, talla];

    this.actualizarProductoCampo('talla', siguiente.join(', '));
  }

  tallaSeleccionada(valor: string): boolean {
    return this.obtenerTallasSeleccionadas().includes(valor);
  }

  guardarProducto(): void {
    const producto = this.productoActual();
    
    // PAYLOAD BLINDADO: Aseguramos que todos los campos tengan valores válidos
    const payload = {
      id: producto.id ? Number(producto.id) : undefined,
      nombre: (producto.nombre ?? '').toString().trim(),
      genero: (producto.genero ?? 'Unisex').toString(),
      talla: (producto.talla ?? '').toString().trim(),
      stock: Number(producto.stock ?? 0),
      precio: Number(producto.precio ?? 0),
      precio_costo: Number(producto.precio_costo ?? 0),
      categoria_id: producto.categoria_id ? Number(producto.categoria_id) : null,
      imagen: (producto.imagen ?? '').toString().trim()
    };

    if (!payload.nombre || payload.precio_costo <= 0) {
      Swal.fire({ icon: 'warning', title: 'Datos incompletos', text: 'Nombre y Costo son obligatorios.', confirmButtonColor: '#d97706' });
      return;
    }

    // LÓGICA DE BIFURCACIÓN: Si hay ID, es PUT (editar). Si no, es POST (crear).
    const request$ = payload.id 
      ? this.apiService.editarProducto(payload) 
      : this.apiService.crearProducto(payload);

    request$.subscribe({
      next: (response: any) => {
        if (response && (response.error || response.success === false)) {
          Swal.fire({ icon: 'error', title: 'Error', text: response?.message || 'Error al guardar.' });
          return;
        }
        Swal.fire({ icon: 'success', title: 'Éxito', text: 'Producto guardado correctamente.', confirmButtonColor: '#d97706' });
        this.cerrarModal();
        this.obtenerProductos();
      },
      error: () => Swal.fire({ icon: 'error', title: 'Error de conexión', text: 'Intenta nuevamente.' })
    });
  }

  async eliminarProducto(id: number) {
    const result = await Swal.fire({
      icon: 'warning', title: '¿Estás seguro?', text: 'Esta acción no se puede deshacer',
      showCancelButton: true, confirmButtonText: 'Sí, eliminar', cancelButtonText: 'Cancelar',
      confirmButtonColor: '#d33', cancelButtonColor: '#1e3a8a'
    });
    if (!result.isConfirmed) return;

    this.apiService.eliminarProducto(id).subscribe({
      next: () => {
        Swal.fire({ icon: 'success', title: 'Eliminado', text: 'Producto borrado.', confirmButtonColor: '#1e3a8a' });
        this.obtenerProductos();
      }
    });
  }

  async registrarVenta(producto: any) {
    const result = await Swal.fire({
      title: `Vender: ${producto?.nombre}`,
      input: 'number', inputLabel: 'Cantidad', inputValue: 1,
      showCancelButton: true, confirmButtonText: 'Vender', confirmButtonColor: '#059669'
    });
    if (!result.isConfirmed) return;

    this.apiService.registrarVenta({ producto_id: producto.id, cantidad: Number(result.value) }).subscribe({
      next: (res: any) => {
        if (res?.success === false) {
          Swal.fire({ icon: 'warning', title: 'Error', text: res?.message });
          return;
        }
        Swal.fire({ icon: 'success', title: 'Vendido', text: 'Venta registrada.', confirmButtonColor: '#059669' });
        this.obtenerProductos();
        this.cargarContabilidad();
      }
    });
  }

  abrirModalCat(cat?: any) {
    this.categoriaActual.set(cat ? { ...cat } : { nombre: '' });
    this.mostrarModalCat.set(true);
  }

  cerrarModalCat() {
    this.mostrarModalCat.set(false);
  }

  guardarCategoria() {
    const cat = this.categoriaActual();
    const request$ = cat.id ? this.apiService.editarCategoria(cat) : this.apiService.crearCategoria(cat);
    request$.subscribe({
      next: () => {
        Swal.fire({ icon: 'success', title: 'Éxito', text: 'Categoría guardada.' });
        this.cerrarModalCat();
        this.obtenerCategorias();
      }
    });
  }

  async eliminarCategoria(id: number) {
    const result = await Swal.fire({
      icon: 'warning', title: '¿Eliminar?', text: 'Se borrará permanentemente.',
      showCancelButton: true, confirmButtonText: 'Sí, eliminar', confirmButtonColor: '#1e3a8a'
    });
    if (!result.isConfirmed) return;
    this.apiService.eliminarCategoria(id).subscribe({
      next: (res: any) => {
        if (res?.success) {
          Swal.fire({ icon: 'success', title: 'Eliminada', text: 'Categoría borrada.' });
          this.obtenerCategorias();
        } else {
          Swal.fire({ icon: 'warning', title: 'No se pudo', text: res?.message });
        }
      }
    });
  }

  cerrarSesion(): void {
    // ✅ V-04 + V-07: AuthService destruye la sesión en el SERVIDOR y limpia sessionStorage
    this.authService.logout();
  }

  private sincronizarTallasConReglas(): void {
    const tallasPermitidas = this.obtenerListaTallas();
    const seleccionadas = this.obtenerTallasSeleccionadas();

    if (tallasPermitidas.length === 0) {
      this.productoActual.set({
        ...this.productoActual(),
        talla: ''
      });
      return;
    }

    const validas = seleccionadas.filter((talla) => tallasPermitidas.includes(talla));
    const actual = seleccionadas.join(', ');
    const siguiente = validas.join(', ');

    if (actual !== siguiente) {
      this.productoActual.set({
        ...this.productoActual(),
        talla: siguiente
      });
    }
  }

  private normalizarTexto(texto: string): string {
    return (texto ?? '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();
  }

  private esCategoriaSinTallas(nombreCategoria: string): boolean {
    return nombreCategoria.includes('cartera')
      || nombreCategoria.includes('gorra')
      || nombreCategoria.includes('reloj')
      || nombreCategoria.includes('accesorio');
  }

  private cargarUsuarioDesdeSesion(): void {
    const usuarioSesion = this.obtenerUsuarioSesion();
    const nombre = (usuarioSesion?.nombre ?? this.authService.getUserName() ?? '').toString().trim();
    this.userName.set(nombre || 'Invitado');

    if (nombre) {
      this.usuarioLogueado.set({
        ...this.usuarioLogueado(),
        nombre
      });
      return;
    }

    this.usuarioLogueado.set({
      ...this.usuarioLogueado(),
      nombre: 'Invitado'
    });
  }

  private obtenerUsuarioSesion(): { nombre?: string } | null {
    if (typeof sessionStorage === 'undefined') {
      return null;
    }

    const raw = sessionStorage.getItem('user');
    if (!raw) {
      return null;
    }

    try {
      const parsed = JSON.parse(raw);
      return typeof parsed === 'object' && parsed !== null ? parsed : null;
    } catch {
      return null;
    }
  }
}

