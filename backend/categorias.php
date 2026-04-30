<?php
/**
 * categorias.php — VERSIÓN SEGURA
 *
 * Correcciones aplicadas:
 * ✅ V-02: Todas las consultas DELETE/SELECT con parámetro usan Prepared Statements
 * ✅ V-03: CORS restrictivo
 * ✅ V-04: requireAuth() para operaciones de escritura
 * ✅ V-05: Credenciales centralizadas
 * ✅ V-14: Bloque DELETE duplicado eliminado
 */

require_once 'db.php';

setCorsHeaders(['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']);
setSecurityHeaders();

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// ✅ V-04: GET es público (muestra categorías en la tienda).
// Las operaciones de escritura requieren autenticación.
if (in_array($_SERVER['REQUEST_METHOD'], ['POST', 'PUT', 'DELETE'], true)) {
    requireAuth();
}

$conn = getConnection();

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    // Sin parámetros de usuario — seguro
    $sql = "SELECT c.id, c.nombre, COUNT(p.id) as total_productos
            FROM categorias c LEFT JOIN productos p ON c.id = p.categoria_id
            GROUP BY c.id ORDER BY c.id DESC";
    $result = $conn->query($sql);
    $data = [];
    while ($row = $result->fetch_assoc()) {
        $data[] = $row;
    }
    echo json_encode($data);
}

elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents("php://input"));
    if (empty($data->nombre)) {
        http_response_code(400);
        echo json_encode(["success" => false, "message" => "El nombre es requerido"]);
        $conn->close();
        exit;
    }
    $stmt = $conn->prepare("INSERT INTO categorias (nombre) VALUES (?)");
    $stmt->bind_param("s", $data->nombre);
    echo json_encode(["success" => $stmt->execute()]);
    $stmt->close();
}

elseif ($_SERVER['REQUEST_METHOD'] === 'PUT') {
    $data = json_decode(file_get_contents("php://input"));
    if (!isset($data->id) || !isset($data->nombre) || empty($data->nombre)) {
        http_response_code(400);
        echo json_encode(["success" => false, "message" => "Datos incompletos"]);
        $conn->close();
        exit;
    }
    $id = (int)$data->id;
    $stmt = $conn->prepare("UPDATE categorias SET nombre=? WHERE id=?");
    $stmt->bind_param("si", $data->nombre, $id);
    echo json_encode(["success" => $stmt->execute()]);
    $stmt->close();
}

elseif ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
    // ✅ V-02: Prepared Statement para verificar y eliminar
    $id = (int)($_GET['id'] ?? 0);

    if ($id <= 0) {
        http_response_code(400);
        echo json_encode(["success" => false, "message" => "ID inválido"]);
        $conn->close();
        exit;
    }

    // Verificar si hay productos asociados
    $stmtCheck = $conn->prepare("SELECT COUNT(*) as total FROM productos WHERE categoria_id = ?");
    $stmtCheck->bind_param("i", $id);
    $stmtCheck->execute();
    $total = $stmtCheck->get_result()->fetch_assoc()['total'];
    $stmtCheck->close();

    if ((int)$total > 0) {
        echo json_encode([
            "success" => false,
            "message" => "No puedes eliminar esta categoría porque tiene $total productos asociados. Muévelos o elimínalos primero."
        ]);
    } else {
        // ✅ V-02: DELETE también con Prepared Statement
        $stmtDel = $conn->prepare("DELETE FROM categorias WHERE id = ?");
        $stmtDel->bind_param("i", $id);
        echo json_encode(["success" => $stmtDel->execute()]);
        $stmtDel->close();
    }
    // ✅ V-14: Bloque DELETE duplicado ELIMINADO
}

$conn->close();