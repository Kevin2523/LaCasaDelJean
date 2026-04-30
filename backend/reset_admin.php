<?php
require_once 'db.php';
$conn = getConnection();

// La contraseña que TÚ elijas (ponla entre las comillas)
$password_nueva = 'admin@123'; 

$hash = password_hash($password_nueva, PASSWORD_BCRYPT);

$stmt = $conn->prepare("UPDATE usuarios SET password = ? WHERE correo = 'admin@lacasadeljean.com'");
$stmt->bind_param("s", $hash);

if ($stmt->execute()) {
    echo "✅ Contraseña actualizada. Tu nueva clave es: <b>$password_nueva</b><br>";
    echo "Sugerencia: Intenta loguearte ahora y luego BORRA este archivo.";
} else {
    echo "❌ Error al actualizar: " . $conn->error;
}
?>