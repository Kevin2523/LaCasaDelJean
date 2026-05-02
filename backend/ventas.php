<?php
/**
 * ventas.php — VERSIÓN SEGURA
 *
 * Correcciones aplicadas:
 * ✅ V-02: Todas las consultas usan Prepared Statements (eliminada interpolación directa)
 * ✅ V-03: CORS restrictivo
 * ✅ V-04: requireAuth() — solo usuarios autenticados pueden registrar ventas
 * ✅ V-05: Credenciales centralizadas
 */

require_once 'db.php';

setCorsHeaders(['GET', 'POST', 'OPTIONS']);
setSecurityHeaders();

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// ✅ V-04: Proteger endpoint con autenticación
requireAuth();

$conn = getConnection();

// POST: Registrar una nueva venta
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents("php://input"));

    // Validar entrada antes de usar
    $producto_id = (int)($data->producto_id ?? 0);
    $cantidad    = (int)($data->cantidad ?? 0);

    if ($producto_id <= 0 || $cantidad <= 0) {
        http_response_code(400);
        echo json_encode(["success" => false, "message" => "Datos inválidos"]);
        $conn->close();
        exit;
    }

    // ✅ V-02: Prepared Statement — ya no es vulnerable a SQL Injection
    $stmtProd = $conn->prepare("SELECT precio, precio_costo, stock FROM productos WHERE id = ?");
    $stmtProd->bind_param("i", $producto_id);
    $stmtProd->execute();
    $prod = $stmtProd->get_result()->fetch_assoc();
    $stmtProd->close();

    if (!$prod) {
        http_response_code(404);
        echo json_encode(["success" => false, "message" => "Producto no encontrado"]);
        $conn->close();
        exit;
    }

    if ((int)$prod['stock'] < $cantidad) {
        echo json_encode(["success" => false, "message" => "Stock insuficiente"]);
        $conn->close();
        exit;
    }

    // Cálculos contables
    $precio_venta  = (float)$prod['precio'];
    $precio_costo  = (float)$prod['precio_costo'];
    $itbms_total   = ($precio_venta * 0.07) * $cantidad;
    $ganancia_neta = (($precio_venta - $precio_costo) * $cantidad) - $itbms_total;

    // Insertar venta
    $stmt = $conn->prepare(
        "INSERT INTO ventas (producto_id, cantidad, precio_venta_momento, precio_costo_momento, itbms_acumulado, ganancia_neta_momento)
         VALUES (?, ?, ?, ?, ?, ?)"
    );
    $stmt->bind_param("iidddd", $producto_id, $cantidad, $precio_venta, $precio_costo, $itbms_total, $ganancia_neta);

    if ($stmt->execute()) {
        // ✅ V-02: UPDATE también con Prepared Statement
        $stmtUpd = $conn->prepare("UPDATE productos SET stock = stock - ? WHERE id = ?");
        $stmtUpd->bind_param("ii", $cantidad, $producto_id);
        $stmtUpd->execute();
        $stmtUpd->close();
        echo json_encode(["success" => true]);
    } else {
        echo json_encode(["success" => false, "message" => "Error al registrar la venta"]);
    }

    $stmt->close();
}

// GET: Obtener resumen mensual para contabilidad
elseif ($_SERVER['REQUEST_METHOD'] === 'GET') {
    // Esta consulta no tiene parámetros del usuario, es segura
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
    while ($row = $result->fetch_assoc()) {
        $reporte[] = $row;
    }
    echo json_encode($reporte);
}

$conn->close();