<?php
/**
 * logout.php — Cerrar sesión de forma segura
 * Destruye la sesión PHP del lado del servidor.
 */

require_once 'db.php';

setCorsHeaders(['POST', 'OPTIONS']);
setSecurityHeaders();

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

// Destruir sesión completa
$_SESSION = [];
session_destroy();

echo json_encode(["success" => true, "message" => "Sesión cerrada"]);
