<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

$conn = new mysqli("localhost", "root", "", "lacasadeljean");

// POST: Registrar una nueva venta
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents("php://input"));
    
    // 1. Obtener datos actuales del producto
    $prod = $conn->query("SELECT precio, precio_costo, stock FROM productos WHERE id = $data->producto_id")->fetch_assoc();
    
    if ($prod['stock'] < $data->cantidad) {
        echo json_encode(["success" => false, "message" => "Stock insuficiente"]);
        exit;
    }

    // 2. Cálculos contables (Reglas de Negocio)
    $precio_venta = $prod['precio'];
    $precio_costo = $prod['precio_costo'];
    $cantidad = $data->cantidad;
    
    $itbms_unitario = $precio_venta * 0.07;
    $itbms_total = $itbms_unitario * $cantidad;
    $ganancia_neta = (($precio_venta - $precio_costo) * $cantidad) - $itbms_total;

    // 3. Insertar en tabla ventas
    $stmt = $conn->prepare("INSERT INTO ventas (producto_id, cantidad, precio_venta_momento, precio_costo_momento, itbms_acumulado, ganancia_neta_momento) VALUES (?, ?, ?, ?, ?, ?)");
    $stmt->bind_param("iidddd", $data->producto_id, $cantidad, $precio_venta, $precio_costo, $itbms_total, $ganancia_neta);
    
    if ($stmt->execute()) {
        // 4. Restar stock del producto
        $conn->query("UPDATE productos SET stock = stock - $cantidad WHERE id = $data->producto_id");
        echo json_encode(["success" => true]);
    } else {
        echo json_encode(["success" => false]);
    }
} 
// GET: Obtener resumen mensual para contabilidad
elseif ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $sql = "SELECT 
                MONTHNAME(fecha_venta) as mes, 
                SUM(precio_venta_momento * cantidad) as total_vendido,
                SUM(itbms_acumulado) as total_itbms,
                SUM(ganancia_neta_momento) as utilidad_real
            FROM ventas 
            GROUP BY MONTH(fecha_venta)
            ORDER BY fecha_venta DESC";
    $result = $conn->query($sql);
    $reporte = [];
    while($row = $result->fetch_assoc()) { $reporte[] = $row; }
    echo json_encode($reporte);
}
$conn->close();
?>