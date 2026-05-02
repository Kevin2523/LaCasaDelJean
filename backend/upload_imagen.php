<?php
/**
 * upload_imagen.php - Endpoint para subir imágenes de productos
 * Guarda las imágenes en /backend/uploads/productos/
 */
require_once __DIR__ . '/db.php';
setCorsHeaders(['POST', 'OPTIONS']);

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(["error" => "Método no permitido"]);
    exit;
}

// Directorio de destino
$uploadDir = __DIR__ . '/uploads/productos/';

// Crear el directorio si no existe
if (!is_dir($uploadDir)) {
    mkdir($uploadDir, 0755, true);
}

// Verificar que se envió un archivo
if (!isset($_FILES['imagen']) || $_FILES['imagen']['error'] !== UPLOAD_ERR_OK) {
    $errorCode = $_FILES['imagen']['error'] ?? -1;
    http_response_code(400);
    echo json_encode(["error" => "No se recibió el archivo o hubo un error al subirlo.", "code" => $errorCode]);
    exit;
}

$archivo = $_FILES['imagen'];

// Validar tipo MIME
$tiposPermitidos = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
$finfo = finfo_open(FILEINFO_MIME_TYPE);
$tipoReal = finfo_file($finfo, $archivo['tmp_name']);
finfo_close($finfo);

if (!in_array($tipoReal, $tiposPermitidos)) {
    http_response_code(400);
    echo json_encode(["error" => "Tipo de archivo no permitido. Solo se aceptan: JPG, PNG, WebP, GIF."]);
    exit;
}

// Validar tamaño (máximo 5 MB)
$maxSize = 5 * 1024 * 1024;
if ($archivo['size'] > $maxSize) {
    http_response_code(400);
    echo json_encode(["error" => "La imagen es demasiado grande. Máximo 5 MB."]);
    exit;
}

// Generar nombre único
$extension = match ($tipoReal) {
    'image/jpeg' => 'jpg',
    'image/png'  => 'png',
    'image/webp' => 'webp',
    'image/gif'  => 'gif',
    default      => 'jpg',
};

$nombreArchivo = 'prod_' . time() . '_' . bin2hex(random_bytes(4)) . '.' . $extension;
$rutaDestino = $uploadDir . $nombreArchivo;

// Mover el archivo
if (!move_uploaded_file($archivo['tmp_name'], $rutaDestino)) {
    http_response_code(500);
    echo json_encode(["error" => "No se pudo guardar la imagen en el servidor."]);
    exit;
}

// Generar la URL pública de la imagen
$urlPublica = 'http://localhost/LaCasaDelJean/backend/uploads/productos/' . $nombreArchivo;

echo json_encode([
    "success" => true,
    "url" => $urlPublica,
    "nombre" => $nombreArchivo
]);
