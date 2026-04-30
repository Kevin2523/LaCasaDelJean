-- ============================================================
-- Script de Base de Datos - LaCasaDelJean
-- Generado por ingeniería inversa desde el backend PHP
-- ============================================================

CREATE DATABASE IF NOT EXISTS `lacasadeljean` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `lacasadeljean`;

-- --------------------------------------------------------
-- 1. Tabla de Configuración
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `configuracion` (
  `clave` VARCHAR(50) NOT NULL,
  `valor` TEXT DEFAULT NULL,
  PRIMARY KEY (`clave`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- 2. Tabla de Usuarios
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(100) NOT NULL,
  `correo` VARCHAR(150) NOT NULL,
  -- REQUERIMIENTO CRÍTICO: VARCHAR(255) para soportar hashes Bcrypt
  `password` VARCHAR(255) NOT NULL, 
  PRIMARY KEY (`id`),
  UNIQUE KEY `correo_unico` (`correo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- 3. Tabla de Categorías
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `categorias` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- 4. Tabla de Productos
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `productos` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `nombre` VARCHAR(150) NOT NULL,
  `genero` VARCHAR(50) DEFAULT 'Unisex',
  `talla` VARCHAR(100) DEFAULT NULL,
  `stock` INT(11) NOT NULL DEFAULT 0,
  `precio` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `precio_costo` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `categoria_id` INT(11) DEFAULT NULL,
  -- REQUERIMIENTO CRÍTICO: LONGTEXT para soportar imágenes en Base64
  `imagen` LONGTEXT DEFAULT NULL, 
  `estado` TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `fk_categoria` (`categoria_id`),
  CONSTRAINT `fk_producto_categoria` FOREIGN KEY (`categoria_id`) REFERENCES `categorias` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- 5. Tabla de Ventas
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `ventas` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `producto_id` INT(11) DEFAULT NULL,
  `cantidad` INT(11) NOT NULL DEFAULT 1,
  `precio_venta_momento` DECIMAL(10,2) NOT NULL,
  `precio_costo_momento` DECIMAL(10,2) NOT NULL,
  `itbms_acumulado` DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  `ganancia_neta_momento` DECIMAL(10,2) NOT NULL,
  `fecha_venta` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_venta_producto` (`producto_id`),
  -- ON DELETE SET NULL permite borrar un producto sin perder el historial de contabilidad
  CONSTRAINT `fk_venta_producto` FOREIGN KEY (`producto_id`) REFERENCES `productos` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- --------------------------------------------------------
-- 6. Tabla de Pagos de Municipio (Mencionada en contabilidad.php)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS `pagos_municipio` (
  `id` INT(11) NOT NULL AUTO_INCREMENT,
  `mes` INT(2) NOT NULL,
  `anio` INT(4) NOT NULL,
  `monto_pagado` DECIMAL(10,2) NOT NULL,
  `fecha_registro` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Inserción de Datos Iniciales
-- ============================================================

-- Configuración de WhatsApp
INSERT INTO `configuracion` (`clave`, `valor`) VALUES 
('wa_principal', '50712345678'),
('wa_secundario', ''),
('wa_plantilla', 'Hola, me interesa este producto:');

-- Usuario administrador de prueba
-- La contraseña es 'admin123' generada de forma segura con Bcrypt
INSERT INTO `usuarios` (`nombre`, `correo`, `password`) VALUES 
('Administrador', 'admin@lacasadeljean.com', '$2y$10$oY7bUv/xVp7Q8rU7oM1l/O0h0W0d1K7X9D5bX9k0m6W6K9x0W9qKq');
