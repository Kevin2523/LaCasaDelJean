<?php
require_once 'db.php';

setCorsHeaders(['GET', 'OPTIONS']);
setSecurityHeaders();
requireAuth();

$conn = getConnection();

$resTotal = $conn->query("SELECT COUNT(*) as total FROM productos");
$total_productos = (int)($resTotal->fetch_assoc()['total'] ?? 0);

$resAlertas = $conn->query("SELECT COUNT(*) as alertas FROM productos WHERE stock = 0");
$alertas_stock = (int)($resAlertas->fetch_assoc()['alertas'] ?? 0);

$resValor = $conn->query("SELECT SUM(precio * stock) as valor_total FROM productos");
$valor_inventario = (float)($resValor->fetch_assoc()['valor_total'] ?? 0);
$valor_inventario = round($valor_inventario, 2);

$resUltimos = $conn->query("SELECT nombre, stock, estado FROM productos ORDER BY id DESC LIMIT 5");
$ultimos_agregados = [];
while ($row = $resUltimos->fetch_assoc()) {
    $row['stock'] = (int)$row['stock'];
    $row['estado'] = (bool)$row['estado'];
    $ultimos_agregados[] = $row;
}

echo json_encode([
    'total_productos' => $total_productos,
    'alertas_stock' => $alertas_stock,
    'valor_inventario' => $valor_inventario,
    'ultimos_agregados' => $ultimos_agregados,
]);

$conn->close();
?>

