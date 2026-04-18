<?php
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type");
header("Content-Type: application/json; charset=UTF-8");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') { http_response_code(200); exit; }

$conn = new mysqli("localhost", "root", "", "lacasadeljean");
$conn->set_charset("utf8");

$data = json_decode(file_get_contents("php://input"), true);

if (!empty($data['correo']) && !empty($data['password'])) {
    $correo = $conn->real_escape_string($data['correo']);
    $pass = $data['password'];

    // Consulta usando la columna 'password'
    $sql = "SELECT id, password FROM usuarios WHERE correo = '$correo' LIMIT 1";
    $result = $conn->query($sql);

    if ($result->num_rows > 0) {
        $user = $result->fetch_assoc();
        if ($pass === $user['password']) { 
            echo json_encode(["status" => "success", "message" => "Login correcto"]);
        } else {
            echo json_encode(["status" => "error", "message" => "Contraseña incorrecta"]);
        }
    } else {
        echo json_encode(["status" => "error", "message" => "Usuario no encontrado"]);
    }
}
$conn->close();
?>