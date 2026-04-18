<?php
header("Access-Control-Allow-Origin: *");
header("Content-Type: application/json; charset=UTF-8");
$conn = new mysqli("localhost", "root", "", "lacasadeljean");
$conn->set_charset("utf8");

// Buscamos las filas de WhatsApp principal y la Plantilla
$sql = "SELECT clave, valor FROM configuracion WHERE clave IN ('wa_principal', 'wa_plantilla')";
$result = $conn->query($sql);

$config = [];
while($row = $result->fetch_assoc()) {
    $config[$row['clave']] = $row['valor'];
}

// Esto devolverá algo como: {"wa_principal": "507699...", "wa_plantilla": "Hola..."}
echo json_encode($config);
$conn->close();
?>