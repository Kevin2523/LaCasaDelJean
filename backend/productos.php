<?php
/**
 * productos.php — VERSIÓN SEGURA
 *
 * Correcciones aplicadas:
 * ✅ V-02: DELETE ahora usa Prepared Statement (antes era $id directo en query)
 * ✅ V-03: CORS restrictivo
 * ✅ V-04: requireAuth() para POST, PUT, DELETE
 * ✅ V-05: Credenciales centralizadas
 */

require_once 'db.php';

setCorsHeaders(['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']);
setSecurityHeaders();

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// ✅ V-04: GET es público (catálogo de tienda). Escrituras requieren auth.
if (in_array($_SERVER['REQUEST_METHOD'], ['POST', 'PUT', 'DELETE'], true)) {
    requireAuth();
}

$conn = getConnection();

// GET: Listado completo (sin parámetros del usuario — seguro)
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $sql = "SELECT p.*, c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            ORDER BY p.id DESC";
    $result = $conn->query($sql);
    $data = [];
    while ($row = $result->fetch_assoc()) {
        $row['estado'] = (bool)$row['estado'];
        $data[] = $row;
    }
    echo json_encode($data);
}

// POST: Crear producto
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents("php://input"));
    if (empty($data->nombre) || !isset($data->precio_costo)) {
        http_response_code(400);
        echo json_encode(["success" => false, "message" => "Nombre y costo son requeridos"]);
        $conn->close();
        exit;
    }
    $stmt = $conn->prepare(
        "INSERT INTO productos (nombre, genero, talla, stock, precio, precio_costo, categoria_id, imagen, estado)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)"
    );
    $stmt->bind_param(
        "sssiddis",
        $data->nombre, $data->genero, $data->talla, $data->stock,
        $data->precio, $data->precio_costo, $data->categoria_id, $data->imagen
    );
    echo json_encode(["success" => $stmt->execute(), "id" => $conn->insert_id]);
    $stmt->close();
}

// PUT: Actualizar producto
elseif ($_SERVER['REQUEST_METHOD'] === 'PUT') {
    $data = json_decode(file_get_contents("php://input"));
    if (empty($data->id)) {
        http_response_code(400);
        echo json_encode(["success" => false, "message" => "ID requerido"]);
        $conn->close();
        exit;
    }
    $stmt = $conn->prepare(
        "UPDATE productos SET nombre=?, genero=?, talla=?, stock=?, precio=?, precio_costo=?, categoria_id=?, imagen=?
         WHERE id=?"
    );
    $stmt->bind_param(
        "sssiddisi",
        $data->nombre, $data->genero, $data->talla, $data->stock,
        $data->precio, $data->precio_costo, $data->categoria_id, $data->imagen, $data->id
    );
    echo json_encode(["success" => $stmt->execute()]);
    $stmt->close();
}

// DELETE: ✅ V-02 — Ahora usa Prepared Statement (antes: query directa con $id)
elseif ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
    $id = (int)($_GET['id'] ?? 0);
    if ($id <= 0) {
        http_response_code(400);
        echo json_encode(["success" => false, "message" => "ID inválido"]);
        $conn->close();
        exit;
    }
    $stmt = $conn->prepare("DELETE FROM productos WHERE id = ?");
    $stmt->bind_param("i", $id);
    echo json_encode(["success" => $stmt->execute()]);
    $stmt->close();
}

$conn->close();