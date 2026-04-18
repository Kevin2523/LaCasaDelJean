<?php
header("Access-Control-Allow-Origin: *");
header("Content-Type: application/json; charset=UTF-8");

$conn = new mysqli("localhost", "root", "", "lacasadeljean");

// Total de productos
$resTotal = $conn->query("SELECT COUNT(*) as total FROM productos");
$total_productos = $resTotal->fetch_assoc()['total'];

// Alertas de stock (stock = 0)
$resAlertas = $conn->query("SELECT COUNT(*) as alertas FROM productos WHERE stock = 0");
$alertas_stock = $resAlertas->fetch_assoc()['alertas'];

// NUEVO: Valor total del inventario (Precio * Stock)
$resValor = $conn->query("SELECT SUM(precio * stock) as valor_total FROM productos");
$valor_inventario = $resValor->fetch_assoc()['valor_total'];
$valor_inventario = $valor_inventario ? round($valor_inventario, 2) : 0; // Si es nulo, devuelve 0

// Últimos agregados
$resUltimos = $conn->query("SELECT nombre, stock, estado FROM productos ORDER BY id DESC LIMIT 5");
$ultimos_agregados = [];
while($row = $resUltimos->fetch_assoc()) {
    $row['estado'] = (bool)$row['estado'];
    $ultimos_agregados[] = $row;
}

echo json_encode([
    "total_productos" => $total_productos,
    "alertas_stock" => $alertas_stock,
    "valor_inventario" => $valor_inventario, // Agregado a la respuesta
    "ultimos_agregados" => $ultimos_agregados
]);
$conn->close();
?> 