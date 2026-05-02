<?php
/**
 * db.php - Conexion centralizada a la base de datos
 */

define('DB_HOST', 'localhost');
define('DB_USER', 'root');
define('DB_PASS', '');
define('DB_NAME', 'lacasadeljean');
define('APP_ENV', 'development');

define('ALLOWED_ORIGINS', [
    'http://localhost:4200',
    'https://tu-dominio-real.com',
]);

function getConnection(): mysqli {
    $conn = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);

    if ($conn->connect_error) {
        http_response_code(500);
        echo json_encode(["error" => "Error interno del servidor"]);
        exit;
    }

    $conn->set_charset("utf8mb4");
    return $conn;
}

function setCorsHeaders(array $methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']): void {
    header("Content-Type: application/json; charset=UTF-8");

    if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
        http_response_code(200);
        exit;
    }
}

function setSecurityHeaders(): void {
    // Las cabeceras de seguridad ya están definidas en .htaccess
}

function requireAuth(): void {
    if (session_status() === PHP_SESSION_NONE) {
        session_start();
    }

    if (empty($_SESSION['usuario_id'])) {
        http_response_code(401);
        echo json_encode(["error" => "No autorizado. Inicia sesion para continuar."]);
        exit;
    }
}

function getAuthUserId(): int {
    return (int)($_SESSION['usuario_id'] ?? 0);
}

