<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

$conn = new mysqli("localhost", "root", "", "lacasadeljean");
$conn->set_charset("utf8");

// GET: Ahora es un simple SELECT ya que todo está en una tabla
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $sql = "SELECT p.*, c.nombre as categoria_nombre FROM productos p 
            LEFT JOIN categorias c ON p.categoria_id = c.id ORDER BY p.id DESC";
    $result = $conn->query($sql);
    $data = [];
    while($row = $result->fetch_assoc()) { 
        $row['estado'] = (bool)$row['estado']; 
        $data[] = $row; 
    }
    echo json_encode($data);
}

// POST: Guarda todo en una sola tabla (Tallas como string)
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents("php://input"));
    $stmt = $conn->prepare("INSERT INTO productos (nombre, genero, talla, stock, precio, precio_costo, categoria_id, imagen, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)");
    $stmt->bind_param("sssiddis", 
        $data->nombre, $data->genero, $data->talla, $data->stock, 
        $data->precio, $data->precio_costo, $data->categoria_id, $data->imagen
    );
    echo json_encode(["success" => $stmt->execute(), "id" => $conn->insert_id]);
}

// PUT: Actualiza todo directamente
elseif ($_SERVER['REQUEST_METHOD'] === 'PUT') {
    $data = json_decode(file_get_contents("php://input"));
    $stmt = $conn->prepare("UPDATE productos SET nombre=?, genero=?, talla=?, stock=?, precio=?, precio_costo=?, categoria_id=?, imagen=? WHERE id=?");
    $stmt->bind_param("sssiddisi", 
        $data->nombre, $data->genero, $data->talla, $data->stock, 
        $data->precio, $data->precio_costo, $data->categoria_id, $data->imagen, $data->id
    );
    echo json_encode(["success" => $stmt->execute()]);
}

// DELETE: Sigue igual
elseif ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
    $id = (int)$_GET['id'];
    echo json_encode(["success" => $conn->query("DELETE FROM productos WHERE id = $id")]);
}
$conn->close();
?>