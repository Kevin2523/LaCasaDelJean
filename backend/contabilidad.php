<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { 
    http_response_code(200); 
    exit; 
}

$conn = new mysqli("localhost", "root", "", "lacasadeljean");
$conn->set_charset("utf8");

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents("php://input"));
    $stmt = $conn->prepare("INSERT INTO pagos_municipio (mes, anio, monto_pagado) VALUES (?, ?, ?)");
    $stmt->bind_param("iid", $data->mes, $data->anio, $data->monto);
    echo json_encode(["success" => $stmt->execute()]);
} 

elseif ($_SERVER['REQUEST_METHOD'] === 'GET') {
    // Operación matemática pura: Ventas por un lado, Inversión por otro
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
        1 => "Enero", 2 => "Febrero", 3 => "Marzo", 4 => "Abril",
        5 => "Mayo", 6 => "Junio", 7 => "Julio", 8 => "Agosto",
        9 => "Septiembre", 10 => "Octubre", 11 => "Noviembre", 12 => "Diciembre"
    ];

    while($row = $result->fetch_assoc()) {
        $m = (int)$row['mes'];
        
        $ventas = (float)$row['ventas_totales'];      // Ejemplo: 180
        $inversion = (float)$row['inversion_total'];  // Ejemplo: 75
        $municipio = (float)$row['total_municipio'];

        // GANANCIA REAL = (Lo que vendiste) - (Lo que te costó) - (Gasto municipal)
        $ganancia_real = $ventas - $inversion - $municipio;

        $datos[] = [
            "mes_nombre" => $mesesEs[$m] . " / " . $row['anio'],
            "ventas_totales" => $ventas,
            "inversion_total" => $inversion,
            "gasto_municipal" => $municipio,
            "ganancia_real" => $ganancia_real
        ];
    }
    echo json_encode($datos);
}
$conn->close();
?>