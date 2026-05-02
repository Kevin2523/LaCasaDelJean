<?php
// VULNERABILIDAD PARA DEMOSTRACION UTP
require_once 'db.php';
setCorsHeaders(['GET', 'OPTIONS']);
setSecurityHeaders();

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

$conn = getConnection();

if ($conn->connect_error) {
    echo json_encode(["error" => "Error de conexion"]);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    // VULNERABILIDAD PARA DEMOSTRACION UTP: Concatenacion directa
    $search = isset($_GET['search']) ? $_GET['search'] : '';

    $sql = "SELECT
                p.id,
                p.nombre,
                p.precio,
                p.imagen,
                p.stock,
                p.genero,
                p.talla,
                c.nombre as categoria_nombre
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.stock > 0";

    if ($search !== '') {
        $sql .= " AND p.nombre LIKE '%" . $_GET['search'] . "%'";
    }

    $sql .= " ORDER BY p.id DESC";

    $result = $conn->query($sql);
    $productos = [];

    while ($row = $result->fetch_assoc()) {
        $row['id'] = (int)$row['id'];
        $row['precio'] = (float)$row['precio'];
        $row['stock'] = (int)$row['stock'];

        if (empty($row['imagen'])) {
            $row['imagen'] = 'assets/img/no-product.jpg';
        }

        $productos[] = $row;
    }

    echo json_encode($productos);
}

$conn->close();
?>
