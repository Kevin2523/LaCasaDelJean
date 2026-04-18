<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: GET, POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { exit; }

$conn = new mysqli("localhost", "root", "", "lacasadeljean");
$conn->set_charset("utf8");

$data = json_decode(file_get_contents("php://input"));

// --- OBTENER DATOS (GET) ---
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    // Obtenemos config de WhatsApp
    $res = $conn->query("SELECT clave, valor FROM configuracion");
    $config = [];
    while($row = $res->fetch_assoc()) { $config[$row['clave']] = $row['valor']; }
    
    // Aquí podrías obtener el usuario actual (asumimos ID 1 por ahora para el ejemplo)
    $user = $conn->query("SELECT id, nombre, correo FROM usuarios WHERE id = 1")->fetch_assoc();
    
    echo json_encode(["config" => $config, "usuario" => $user]);
}

// --- GUARDAR CONFIG WHATSAPP ---
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data->tipo) && $data->tipo === 'whatsapp') {
    foreach ($data->ajustes as $clave => $valor) {
        $stmt = $conn->prepare("UPDATE configuracion SET valor = ? WHERE clave = ?");
        $stmt->bind_param("ss", $valor, $clave);
        $stmt->execute();
    }
    echo json_encode(["success" => true]);
}

// --- ACTUALIZAR CONTRASEÑA DEL USUARIO ---
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($data->tipo) && $data->tipo === 'perfil') {
    // Solo actualizamos si se envió una nueva contraseña
    if (!empty($data->password)) {
        $stmt = $conn->prepare("UPDATE usuarios SET password = ? WHERE id = ?");
        $stmt->bind_param("si", $data->password, $data->usuario_id);
        echo json_encode(["success" => $stmt->execute()]);
    }
}
$conn->close();
?>