<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

$conn = new mysqli("localhost", "root", "", "lacasadeljean");

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $sql = "SELECT c.id, c.nombre, COUNT(p.id) as total_productos 
            FROM categorias c LEFT JOIN productos p ON c.id = p.categoria_id 
            GROUP BY c.id ORDER BY c.id DESC";
    $result = $conn->query($sql);
    $data = [];
    while($row = $result->fetch_assoc()) { $data[] = $row; }
    echo json_encode($data);
} 
elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents("php://input"));
    $stmt = $conn->prepare("INSERT INTO categorias (nombre) VALUES (?)");
    $stmt->bind_param("s", $data->nombre);
    echo json_encode(["success" => $stmt->execute()]);
}
elseif ($_SERVER['REQUEST_METHOD'] === 'PUT') {
    $data = json_decode(file_get_contents("php://input"));
    // Validamos que venga el ID y el nombre
    if(isset($data->id) && isset($data->nombre)) {
        $stmt = $conn->prepare("UPDATE categorias SET nombre=? WHERE id=?");
        $stmt->bind_param("si", $data->nombre, $data->id);
        echo json_encode(["success" => $stmt->execute()]);
    } else {
        echo json_encode(["success" => false, "message" => "Datos incompletos"]);
    }
}
elseif ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
    $id = $_GET['id'];
    
    // 1. Verificamos si hay productos asociados
    $check = $conn->query("SELECT COUNT(*) as total FROM productos WHERE categoria_id = $id");
    $total = $check->fetch_assoc()['total'];
    
    if ($total > 0) {
        // 2. Si hay productos, prohibimos el borrado
        echo json_encode([
            "success" => false, 
            "message" => "No puedes eliminar esta categoría porque tiene $total productos asociados. Muévelos o elimínalos primero."
        ]);
    } else {
        // 3. Si está limpia, procedemos
        $res = $conn->query("DELETE FROM categorias WHERE id = $id");
        echo json_encode(["success" => $res]);
    }
}
elseif ($_SERVER['REQUEST_METHOD'] === 'DELETE') {
    $id = $_GET['id'];
    $conn->query("DELETE FROM categorias WHERE id = $id");
    echo json_encode(["success" => true]);
}
$conn->close();
?>