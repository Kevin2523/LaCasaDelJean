<?php
/**
 * check_session.php — Endpoint para verificar sesión activa
 * Usado por el AuthGuard de Angular para validar contra el servidor.
 * ✅ FIX V-06: La validación de sesión ocurre en el servidor, no solo en localStorage
 */

require_once 'db.php';

setCorsHeaders(['GET', 'OPTIONS']);
setSecurityHeaders();

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

$isValid = !empty($_SESSION['usuario_id']);

echo json_encode([
    "valid"  => $isValid,
    "nombre" => $isValid ? ($_SESSION['usuario_nombre'] ?? 'Administrador') : null
]);
