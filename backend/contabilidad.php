<?php
require_once 'db.php';

setCorsHeaders(['GET', 'POST', 'OPTIONS']);
setSecurityHeaders();
requireAuth();

$conn = getConnection();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents("php://input"));
    $mes = (int)($data->mes ?? 0);
    $anio = (int)($data->anio ?? 0);
    $monto = (float)($data->monto ?? 0);

    if ($mes < 1 || $mes > 12 || $anio < 2000 || $monto < 0) {
        http_response_code(400);
        echo json_encode(['success' => false, 'message' => 'Datos invalidos']);
        $conn->close();
        exit;
    }

    $stmt = $conn->prepare("INSERT INTO pagos_municipio (mes, anio, monto_pagado) VALUES (?, ?, ?)");
    $stmt->bind_param("iid", $mes, $anio, $monto);
    echo json_encode(['success' => $stmt->execute()]);
    $stmt->close();
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $sql = "SELECT
                mes,
                anio,
                SUM(ingreso_bruto) as ventas_totales,
                SUM(gasto_inversion) as inversion_total,
                SUM(pago_mun) as total_municipio
            FROM (
                SELECT
                    MONTH(fecha_venta) as mes,
                    YEAR(fecha_venta) as anio,
                    (precio_venta_momento * cantidad) as ingreso_bruto,
                    (precio_costo_momento * cantidad) as gasto_inversion,
                    0 as pago_mun
                FROM ventas

                UNION ALL

                SELECT
                    mes,
                    anio,
                    0 as ingreso_bruto,
                    0 as gasto_inversion,
                    monto_pagado as pago_mun
                FROM pagos_municipio
            ) as resumen_total
            GROUP BY anio, mes
            ORDER BY anio DESC, mes DESC";

    $result = $conn->query($sql);
    $datos = [];

    $mesesEs = [
        1 => 'Enero', 2 => 'Febrero', 3 => 'Marzo', 4 => 'Abril',
        5 => 'Mayo', 6 => 'Junio', 7 => 'Julio', 8 => 'Agosto',
        9 => 'Septiembre', 10 => 'Octubre', 11 => 'Noviembre', 12 => 'Diciembre'
    ];

    while ($row = $result->fetch_assoc()) {
        $m = (int)$row['mes'];
        $ventas = (float)$row['ventas_totales'];
        $inversion = (float)$row['inversion_total'];
        $municipio = (float)$row['total_municipio'];

        $datos[] = [
            'mes_nombre' => (($mesesEs[$m] ?? 'Mes') . ' / ' . $row['anio']),
            'ventas_totales' => $ventas,
            'inversion_total' => $inversion,
            'gasto_municipal' => $municipio,
            'ganancia_real' => $ventas - $inversion - $municipio,
        ];
    }

    echo json_encode($datos);
}

$conn->close();
?>

