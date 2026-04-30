import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = 'http://localhost/LaCasaDelJean/backend/';

  getDashboard(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}dashboard.php`);
  }

  getProductos(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}productos.php`);
  }

  getProductosCliente(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}productos_cliente.php`);
  }

  getCategorias(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}categorias.php`);
  }

  getConfiguracion(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}configuracion.php`);
  }

  guardarConfiguracion(payload: any): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}configuracion.php`, payload);
  }

  crearProducto(producto: any): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}productos.php`, producto);
  }

  editarProducto(producto: any): Observable<any> {
    return this.http.put<any>(`${this.baseUrl}productos.php`, producto);
  }

  eliminarProducto(id: number): Observable<any> {
    return this.http.delete<any>(`${this.baseUrl}productos.php?id=${id}`);
  }

  crearCategoria(cat: any): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}categorias.php`, cat);
  }

  editarCategoria(cat: any): Observable<any> {
    return this.http.put<any>(`${this.baseUrl}categorias.php`, cat);
  }

  eliminarCategoria(id: number): Observable<any> {
    return this.http.delete<any>(`${this.baseUrl}categorias.php?id=${id}`);
  }

  getContabilidad(): Observable<any[]> {
    return this.http.get<any[]>(`${this.baseUrl}contabilidad.php`);
  }

  registrarPagoMunicipio(payload: { monto: number; mes: number; anio: number }): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}contabilidad.php`, payload);
  }

  registrarVenta(payload: { producto_id: number; cantidad: number }): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}ventas.php`, payload);
  }
}



