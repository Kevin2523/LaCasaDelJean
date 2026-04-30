# 🔐 Reporte de Auditoría de Seguridad — LaCasaDelJean
**Fecha:** 2026-04-26 | **Auditor:** Antigravity (Especialista en OWASP Top 10)  
**Stack:** Angular 18 + PHP (MySQLi) · **Scope:** Monorepo completo

---

## 📊 Resumen Ejecutivo

| # | Vulnerabilidad | Archivo(s) | Criticidad | Estado |
|---|---------------|------------|------------|--------|
| V-01 | Contraseña en texto plano (sin hash) | `login_cliente.php`, `configuracion.php` | 🔴 **CRÍTICO** | Sin corregir |
| V-02 | Inyección SQL directa — ventas/categorias | `ventas.php`, `categorias.php`, `productos.php` | 🔴 **CRÍTICO** | Sin corregir |
| V-03 | CORS abierto a todo el mundo (`*`) | Todos los `.php` | 🔴 **CRÍTICO** | Sin corregir |
| V-04 | Sin autenticación en endpoints de admin | Todos los `.php` | 🔴 **CRÍTICO** | Sin corregir |
| V-05 | Credenciales DB hardcodeadas en cada archivo | Todos los `.php` | 🟠 **ALTO** | Sin corregir |
| V-06 | AuthGuard solo revisa localStorage — bypasseable | `auth.guard.ts` | 🟠 **ALTO** | Sin corregir |
| V-07 | Datos sensibles en localStorage | `admin.ts`, `auth.guard.ts` | 🟠 **ALTO** | Sin corregir |
| V-08 | Sin interceptor HTTP — sin token en peticiones | `api.service.ts` | 🟠 **ALTO** | Sin corregir |
| V-09 | Información de usuario filtrada en respuesta API | `configuracion.php` | 🟡 **MEDIO** | Sin corregir |
| V-10 | Usuario admin hardcodeado (ID=1) | `configuracion.php` | 🟡 **MEDIO** | Sin corregir |
| V-11 | Sin cabeceras de seguridad HTTP | Todos los `.php` | 🟡 **MEDIO** | Sin corregir |
| V-12 | Sin `.htaccess` de protección | `backend/` | 🟡 **MEDIO** | Sin corregir |
| V-13 | Mensajes de error revelan info del sistema | `login_cliente.php` | 🟢 **BAJO** | Sin corregir |
| V-14 | Bloque `DELETE` duplicado en categorias.php | `categorias.php` | 🟢 **BAJO** | Bug lógico |

---

## 🔴 VULNERABILIDADES CRÍTICAS

---

### V-01 — Contraseña guardada en Texto Plano
**OWASP:** A02:2021 – Cryptographic Failures  
**Criticidad:** 🔴 CRÍTICO

**Evidencia en código:**
```php
// login_cliente.php — línea 24
if ($pass === $user['password']) {   // ← Comparación directa, sin hash

// configuracion.php — línea 42
$stmt->bind_param("si", $data->password, $data->usuario_id);  // ← Guarda texto plano
```

**Impacto:** Si la base de datos es comprometida (por SQL Injection u otro vector), **todas las contraseñas quedan expuestas inmediatamente** sin necesidad de crackeo.

**✅ Corrección:**
```php
// AL REGISTRAR un usuario nuevo:
$hash = password_hash($password_plano, PASSWORD_BCRYPT);
// Guardar $hash en DB

// AL HACER LOGIN:
if (password_verify($pass, $user['password'])) { /* OK */ }

// AL ACTUALIZAR contraseña:
$nuevoHash = password_hash($data->nueva_password, PASSWORD_BCRYPT);
$stmt->bind_param("si", $nuevoHash, $data->usuario_id);
```

---

### V-02 — Inyección SQL por Interpolación Directa
**OWASP:** A03:2021 – Injection  
**Criticidad:** 🔴 CRÍTICO

**Evidencia en código:**
```php
// ventas.php — líneas 16 y 38 (DOBLE VULNERABILIDAD en el mismo archivo)
$prod = $conn->query("SELECT ... FROM productos WHERE id = $data->producto_id");
$conn->query("UPDATE productos SET stock = stock - $cantidad WHERE id = $data->producto_id");

// categorias.php — líneas 41, 52, 58
$check = $conn->query("SELECT COUNT(*) ... WHERE categoria_id = $id");
$conn->query("DELETE FROM categorias WHERE id = $id");

// productos.php — línea 50
$conn->query("DELETE FROM productos WHERE id = $id");

// login_cliente.php — línea 15-19 (usa real_escape_string, no prepared statement)
$correo = $conn->real_escape_string($data['correo']);
$sql = "SELECT id, password FROM usuarios WHERE correo = '$correo' LIMIT 1";
```

> ⚠️ `real_escape_string` **no es suficiente** en todos los contextos y no reemplaza a los Prepared Statements.

**Payload de ataque de ejemplo en ventas.php:**
```
POST /ventas.php
{"producto_id": "1; DROP TABLE ventas; --", "cantidad": 1}
```

**✅ Corrección — ventas.php (ejemplo):**
```php
// Reemplazar consulta directa con prepared statement
$stmt = $conn->prepare("SELECT precio, precio_costo, stock FROM productos WHERE id = ?");
$stmt->bind_param("i", $data->producto_id);
$stmt->execute();
$prod = $stmt->get_result()->fetch_assoc();

// UPDATE de stock también:
$stmtUpd = $conn->prepare("UPDATE productos SET stock = stock - ? WHERE id = ?");
$stmtUpd->bind_param("ii", $cantidad, $data->producto_id);
$stmtUpd->execute();
```

---

### V-03 — CORS Completamente Abierto (`Access-Control-Allow-Origin: *`)
**OWASP:** A05:2021 – Security Misconfiguration  
**Criticidad:** 🔴 CRÍTICO

**Evidencia en código:**
```php
// TODOS los archivos PHP — primera línea
header("Access-Control-Allow-Origin: *");
```

**Impacto:** Cualquier sitio web en internet puede hacer peticiones a tu backend y leer las respuestas. Esto elimina toda protección CORS, permitiendo ataques de tipo **CSRF** y robo de datos desde dominios maliciosos.

**✅ Corrección:**
```php
$allowed_origins = ['http://localhost:4200', 'https://tu-dominio-real.com'];
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if (in_array($origin, $allowed_origins)) {
    header("Access-Control-Allow-Origin: $origin");
}
header("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Authorization");
header("Vary: Origin");
```

---

### V-04 — Sin Autenticación en Endpoints del Backend (Broken Access Control)
**OWASP:** A01:2021 – Broken Access Control  
**Criticidad:** 🔴 CRÍTICO

**Evidencia:** **Ningún archivo PHP** verifica si el usuario está autenticado antes de ejecutar operaciones. Cualquier persona con acceso a la red puede:
```bash
# Obtener todos los productos y precios de costo (dato financiero sensible)
curl http://tu-servidor/backend/productos.php

# Eliminar un producto sin estar logueado
curl -X DELETE http://tu-servidor/backend/productos.php?id=5

# Ver todos los datos contables
curl http://tu-servidor/backend/contabilidad.php

# Ver datos de usuarios
curl http://tu-servidor/backend/configuracion.php
```

**✅ Corrección — Implementar verificación de sesión:**
```php
// auth.php — archivo de utilidad a crear
<?php
session_start();
function requireAuth() {
    if (empty($_SESSION['usuario_id'])) {
        http_response_code(401);
        echo json_encode(["error" => "No autorizado"]);
        exit;
    }
}
?>

// En cada endpoint de admin:
require_once 'auth.php';
requireAuth();  // ← Primera línea después de los headers
```

---

## 🟠 VULNERABILIDADES ALTAS

---

### V-05 — Credenciales de Base de Datos Hardcodeadas en Cada Archivo
**OWASP:** A05:2021 – Security Misconfiguration  
**Criticidad:** 🟠 ALTO

**Evidencia:** Las credenciales de DB están repetidas en **los 10 archivos PHP**:
```php
$conn = new mysqli("localhost", "root", "", "lacasadeljean");
//                              ^^^^   ^^
//                              usuario sin contraseña — riesgo extra
```

Además: **el usuario es `root` sin contraseña**, lo que viola el principio de mínimo privilegio.

**✅ Corrección:**
1. Crear un archivo `db.php` centralizado **fuera del webroot** o en una ubicación protegida.
2. Crear un usuario MySQL dedicado con solo los permisos necesarios.
3. Nunca usar `root` en producción.

```php
// db.php
<?php
define('DB_HOST', 'localhost');
define('DB_USER', 'lacasadeljean_user');   // Usuario dedicado
define('DB_PASS', 'contraseña_segura_aquí');
define('DB_NAME', 'lacasadeljean');

function getConnection(): mysqli {
    $conn = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
    $conn->set_charset("utf8mb4");
    if ($conn->connect_error) {
        http_response_code(500);
        echo json_encode(["error" => "Error interno del servidor"]);
        exit;
    }
    return $conn;
}
?>
```

---

### V-06 — AuthGuard Angular Bypasseable (Solo Frontend)
**OWASP:** A01:2021 – Broken Access Control  
**Criticidad:** 🟠 ALTO

**Evidencia en código:**
```typescript
// auth.guard.ts — línea 6
const isLogged = localStorage.getItem('is_logged') === 'true';
```

**Impacto:** Un atacante puede abrir la consola del navegador y ejecutar:
```javascript
localStorage.setItem('is_logged', 'true');
localStorage.setItem('user_name', 'Hacker');
```
Inmediatamente tendrá acceso visual al panel de administración. Aunque el backend no esté protegido, esto revela la interfaz de admin completa.

> ⚠️ El AuthGuard de Angular es solo UX, **nunca seguridad real**. La seguridad DEBE estar en el backend (V-04).

**✅ Corrección — Validación contra el servidor:**
```typescript
// auth.service.ts — nuevo servicio
@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  
  // Verificar sesión activa contra el servidor
  checkSession(): Observable<boolean> {
    return this.http.get<{valid: boolean}>('/backend/check_session.php')
      .pipe(map(r => r.valid), catchError(() => of(false)));
  }
  
  isLoggedIn(): boolean {
    return sessionStorage.getItem('session_token') !== null;
  }
}

// auth.guard.ts — mejorado
export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);
  return authService.checkSession().pipe(
    map(valid => valid ? true : router.createUrlTree(['/']))
  );
};
```

---

### V-07 — Información Sensible en localStorage
**OWASP:** A02:2021 – Cryptographic Failures  
**Criticidad:** 🟠 ALTO

**Evidencia:**
```typescript
// auth.guard.ts — línea 6
localStorage.getItem('is_logged')

// admin.ts — línea 148
localStorage.getItem('user_name')
```

**Impacto:** `localStorage` es accesible desde JavaScript. Cualquier script XSS puede leer y exfiltrar estos valores. Además persiste indefinidamente, no expira con el cierre del navegador.

**✅ Corrección:**
- Usar `sessionStorage` en lugar de `localStorage` (se borra al cerrar la pestaña).
- Mejor aún: usar **cookies HttpOnly** desde el backend para el token de sesión, que son inaccesibles desde JavaScript.
- No guardar `is_logged` como string `'true'` — es trivialmente manipulable.

```typescript
// Nunca usar localStorage para datos de autenticación
// Usar sessionStorage como mínimo, o cookies HttpOnly como óptimo
sessionStorage.setItem('session_token', token_recibido_del_servidor);
```

---

### V-08 — Sin Interceptor HTTP — Peticiones sin Token de Autenticación
**OWASP:** A01:2021 – Broken Access Control  
**Criticidad:** 🟠 ALTO

**Evidencia:** El `api.service.ts` hace todas las peticiones sin ningún header de autenticación. No existe ningún interceptor HTTP en el proyecto.

**✅ Corrección — Crear interceptor Angular:**
```typescript
// auth.interceptor.ts
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const token = sessionStorage.getItem('session_token');
  if (token) {
    const authReq = req.clone({
      headers: req.headers.set('Authorization', `Bearer ${token}`)
    });
    return next(authReq);
  }
  return next(req);
};

// app.config.ts — registrar interceptor
export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(withInterceptors([authInterceptor]))
  ]
};
```

---

## 🟡 VULNERABILIDADES MEDIAS

---

### V-09 — API Filtra Datos del Usuario Innecesariamente
**Criticidad:** 🟡 MEDIO

```php
// configuracion.php — línea 22-24
$user = $conn->query("SELECT id, nombre, correo FROM usuarios WHERE id = 1")->fetch_assoc();
echo json_encode(["config" => $config, "usuario" => $user]);
```
El correo del administrador es devuelto en cada petición GET a `/configuracion.php`, accesible sin autenticación.

**✅ Corrección:** No devolver datos del usuario en este endpoint público. Si es necesario, protegerlo con autenticación y devolver solo el nombre.

---

### V-10 — ID de Usuario Hardcodeado como `1`
**Criticidad:** 🟡 MEDIO

```php
// configuracion.php — línea 22
$user = $conn->query("SELECT ... FROM usuarios WHERE id = 1")->fetch_assoc();
```
Si el sistema crece o el ID cambia, esto falla silenciosamente. En el frontend, el ID también está hardcodeado:
```typescript
// admin.ts — línea 26
usuarioLogueado = signal<any>({ nombre: 'Administrador', id: 1 });
```

**✅ Corrección:** El ID de usuario debe venir de la sesión PHP activa (`$_SESSION['usuario_id']`).

---

### V-11 — Sin Cabeceras de Seguridad HTTP
**OWASP:** A05:2021 – Security Misconfiguration  
**Criticidad:** 🟡 MEDIO

Faltan completamente:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy`
- `Referrer-Policy`
- `Strict-Transport-Security` (HSTS)

---

### V-12 — Sin `.htaccess` de Protección
**Criticidad:** 🟡 MEDIO

No existe ningún `.htaccess` en el backend que proteja archivos de configuración o bloquee acceso directo a scripts no autorizados.

---

## 🟢 VULNERABILIDADES BAJAS

---

### V-13 — Mensajes de Error Informativos
**Criticidad:** 🟢 BAJO

```php
// login_cliente.php — línea 30
echo json_encode(["status" => "error", "message" => "Usuario no encontrado"]);
```
Permite enumerar usuarios válidos. Un atacante puede saber si un email existe en el sistema.

**✅ Corrección:** Usar un mensaje genérico:
```php
echo json_encode(["status" => "error", "message" => "Credenciales incorrectas"]);
```

---

### V-14 — Bloque `DELETE` Duplicado en categorias.php
**Criticidad:** 🟢 BAJO (Bug lógico)

```php
// categorias.php — líneas 37-59 y 56-60
elseif ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
    // primer bloque con validación
}
elseif ($_SERVER['REQUEST_METHOD'] === 'DELETE') {  // ← NUNCA se ejecuta (dead code)
    // segundo bloque sin validación — si fuera alcanzable, sería inseguro
}
```
El segundo `elseif` nunca se ejecuta, pero confunde la lógica y genera code debt.

---

## 🛠️ Plan de Corrección Priorizado

| Prioridad | Tarea | Esfuerzo |
|-----------|-------|----------|
| 1 | Implementar `password_hash` / `password_verify` en login y cambio de contraseña | 30 min |
| 2 | Reemplazar todas las consultas SQL interpoladas con Prepared Statements | 1 hora |
| 3 | Crear `db.php` centralizado y proteger credenciales | 20 min |
| 4 | Implementar sesiones PHP (`session_start`) + middleware de auth | 1 hora |
| 5 | Generar `.htaccess` con headers de seguridad y CORS restrictivo | 20 min |
| 6 | Crear AuthService en Angular que valide contra el servidor | 45 min |
| 7 | Implementar Interceptor HTTP en Angular | 20 min |
| 8 | Migrar de localStorage a sessionStorage/cookies HttpOnly | 30 min |
| 9 | Corregir mensajes de error genéricos | 10 min |
| 10 | Eliminar bloque DELETE duplicado en categorias.php | 5 min |

**Tiempo total estimado de remediación: ~5-6 horas**

---

> ✅ Los archivos corregidos se encuentran en las secciones siguientes del chat.
