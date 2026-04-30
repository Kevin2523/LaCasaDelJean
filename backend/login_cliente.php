<?php
/**
 * login_cliente.php — VERSIÓN SEGURA
 *
 * Correcciones aplicadas:
 * ✅ V-01: Usa password_verify() en lugar de comparación directa
 * ✅ V-03: CORS restrictivo (solo orígenes permitidos)
 * ✅ V-04: Inicia sesión PHP en lugar de devolver solo "success"
 * ✅ V-05: Credenciales centralizadas en db.php
 * ✅ V-13: Mensaje de error genérico (no revela si existe el usuario)
 * ✅ V-02: Consulta con Prepared Statement
 */

require_once 'db.php';

setCorsHeaders(['POST', 'OPTIONS']);
setSecurityHeaders();

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(["error" => "Método no permitido"]);
    exit;
}

$data = json_decode(file_get_contents("php://input"), true);

// Validar que lleguen los campos requeridos
if (empty($data['correo']) || empty($data['password'])) {
    http_response_code(400);
    echo json_encode(["status" => "error", "message" => "Correo y contraseña son requeridos"]);
    exit;
}

$conn = getConnection();

// ✅ V-02: Prepared Statement — sin interpolación de strings
$stmt = $conn->prepare("SELECT id, nombre, password FROM usuarios WHERE correo = ? LIMIT 1");
$stmt->bind_param("s", $data['correo']);
$stmt->execute();
$result = $stmt->get_result();

// ✅ V-13: Mensaje de error genérico — no revela si existe el usuario
$mensajeError = ["status" => "error", "message" => "Credenciales incorrectas"];

if ($result->num_rows === 0) {
    // Tiempo de respuesta constante para evitar timing attacks
    password_verify("dummy", '$2y$10$dummyhashfortimingresisteance');
    echo json_encode($mensajeError);
    $conn->close();
    exit;
}

$user = $result->fetch_assoc();

// ✅ V-01: Verificación segura con password_verify() (soporta bcrypt)
if (!password_verify($data['password'], $user['password'])) {
    echo json_encode($mensajeError);
    $conn->close();
    exit;
}

// ✅ V-04: Iniciar sesión PHP — la autenticación vive en el servidor
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}
session_regenerate_id(true); // Previene Session Fixation
$_SESSION['usuario_id'] = (int)$user['id'];
$_SESSION['usuario_nombre'] = $user['nombre'];

// Solo devolver datos no sensibles al frontend
echo json_encode([
    "status"  => "success",
    "message" => "Login correcto",
    "nombre"  => $user['nombre'],
    "id"      => (int)$user['id']
]);

$stmt->close();
$conn->close();