<?php
require_once 'db.php';

setCorsHeaders(['GET', 'OPTIONS']);
setSecurityHeaders();

$conn = getConnection();
$conn->set_charset('utf8mb4');

$sql = "SELECT clave, valor FROM configuracion WHERE clave IN ('wa_principal', 'wa_plantilla')";
$result = $conn->query($sql);

$config = [];
while ($row = $result->fetch_assoc()) {
    $config[$row['clave']] = $row['valor'];
}

echo json_encode($config);
$conn->close();
?>

