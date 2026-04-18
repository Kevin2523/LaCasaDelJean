<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

$conn = new mysqli("localhost", "root", "", "lacasadeljean");
$conn->set_charset("utf8");

// Consulta corregida para incluir genero y talla
$sql = "SELECT p.id, p.nombre, p.precio, p.imagen, p.genero, p.talla, c.nombre as categoria_nombre 
        FROM productos p
        INNER JOIN (
            SELECT MAX(id) as id 
            FROM productos 
            GROUP BY categoria_id
        ) p_max ON p.id = p_max.id
        LEFT JOIN categorias c ON p.categoria_id = c.id
        WHERE p.stock > 0";

$result = $conn->query($sql);
$destacados = [];

while($row = $result->fetch_assoc()) {
    $row['id'] = (int)$row['id'];
    $row['precio'] = (float)$row['precio'];
    $destacados[] = $row;
}

echo json_encode($destacados);
$conn->close();
?>