<?php
/**
 * configuracion.php — VERSIÓN SEGURA
 *
 * Correcciones aplicadas:
 * ✅ V-01: password_hash() para actualizar contraseña (ya no texto plano)
 * ✅ V-03: CORS restrictivo
 * ✅ V-04: requireAuth() — solo admins autenticados
 * ✅ V-05: Credenciales centralizadas
 * ✅ V-09: No filtrar correo ni datos sensibles del usuario
 * ✅ V-10: ID de usuario viene de la sesión, no hardcodeado como "1"
 */

require_once 'db.php';

setCorsHeaders(['GET', 'POST', 'OPTIONS']);
setSecurityHeaders();

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// ✅ V-04: Todo este endpoint requiere autenticación
requireAuth();

$conn = getConnection();
$data = json_decode(file_get_contents("php://input"));

// ✅ V-10: El ID viene de la sesión, no del cliente ni hardcodeado
$usuarioId = getAuthUserId();

// --- OBTENER DATOS (GET) ---
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $res = $conn->query("SELECT clave, valor FROM configuracion");
    $config = [];
    while ($row = $res->fetch_assoc()) {
        $config[$row['clave']] = $row['valor'];
    }

    // ✅ V-09: Solo devolver nombre, nunca correo ni password
    $stmtUser = $conn->prepare("SELECT id, nombre FROM usuarios WHERE id = ?");
    $stmtUser->bind_param("i", $usuarioId);
    $stmtUser->execute();
    $user = $stmtUser->get_result()->fetch_assoc();
    $stmtUser->close();

    echo json_encode(["config" => $config, "usuario" => $user]);
}

// --- GUARDAR CONFIG WHATSAPP ---
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data->tipo) && $data->tipo === 'whatsapp') {
    foreach ((array)$data->ajustes as $clave => $valor) {
        // Validar que la clave sea una de las permitidas (evitar escritura arbitraria)
        $clavesPermitidas = ['wa_principal', 'wa_secundario', 'wa_plantilla'];
        if (!in_array($clave, $clavesPermitidas, true)) continue;

        $stmt = $conn->prepare("UPDATE configuracion SET valor = ? WHERE clave = ?");
        $stmt->bind_param("ss", $valor, $clave);
        $stmt->execute();
        $stmt->close();
    }
    echo json_encode(["success" => true]);
}

// --- ACTUALIZAR CONTRASEÑA DEL USUARIO ---
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data->tipo) && $data->tipo === 'perfil') {
    if (!empty($data->nueva_password)) {
        $nuevaPassword = (string)$data->nueva_password;

        // Validar longitud mínima
        if (strlen($nuevaPassword) < 8) {
            http_response_code(400);
            echo json_encode(["success" => false, "message" => "La contraseña debe tener al menos 8 caracteres"]);
            $conn->close();
            exit;
        }

        // ✅ V-01: Hashear la contraseña con bcrypt ANTES de guardar
        $hash = password_hash($nuevaPassword, PASSWORD_BCRYPT);

        // ✅ V-10: Usar ID de sesión, ignorar cualquier ID enviado por el cliente
        $stmt = $conn->prepare("UPDATE usuarios SET password = ? WHERE id = ?");
        $stmt->bind_param("si", $hash, $usuarioId);
        echo json_encode(["success" => $stmt->execute()]);
        $stmt->close();
    } else {
        http_response_code(400);
        echo json_encode(["success" => false, "message" => "La contraseña no puede estar vacía"]);
    }
}

$conn->close();