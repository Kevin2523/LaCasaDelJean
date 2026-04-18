<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { 
    http_response_code(200); 
    exit; 
}

$conn = new mysqli("localhost", "root", "", "lacasadeljean");
$conn->set_charset("utf8");

if ($conn->connect_error) {
    echo json_encode(["error" => "Error de conexión"]);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    // Seleccionamos solo las columnas que existen en tu phpMyAdmin
    $sql = "SELECT 
                p.id, 
                p.nombre, 
                p.precio, 
                p.imagen, 
                p.stock,
                p.genero,
                p.talla,
                c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.stock > 0
            ORDER BY p.id DESC";

    $result = $conn->query($sql);
    $productos = [];

    while($row = $result->fetch_assoc()) {
        $row['id'] = (int)$row['id'];
        $row['precio'] = (float)$row['precio'];
        $row['stock'] = (int)$row['stock'];
        
        if (empty($row['imagen'])) {
            $row['imagen'] = 'assets/img/no-product.jpg';
        }

        $productos[] = $row;
    }

    echo json_encode($productos);
}

$conn->close();
?>