# La Casa del Jean - Monorepo

Este repositorio centraliza todo el código fuente de La Casa del Jean, dividido entre el cliente (Frontend) y los servicios de base de datos (Backend).

## Arquitectura de Carpetas

```text
LaCasaDelJean/
│
├── backend/               # Servicios API en PHP y configuración de Base de Datos
│   ├── index.php
│   ├── configuracion.php
│   └── ... (endpoints de API)
│
├── frontend/              # Aplicación cliente y administrador construida en Angular 17+
│   ├── src/
│   │   ├── app/
│   │   │   ├── admin/
│   │   │   ├── client-layout/
│   │   │   ├── home/
│   │   │   └── shop/
│   ├── package.json
│   └── angular.json
│
├── .gitignore             # Configuración global de exclusión de Git
└── README.md              # Documentación principal del monorepo
```

## Pasos de Instalación y Ejecución Rápidos

### Preparación del Entorno
Antes de comenzar, asegúrate de tener instalado:
- **Node.js** (v18+)
- **PHP** (v8+) / XAMPP
- **MySQL** o MariaDB corriendo en el puerto 3306

### Levantando el Frontend (Angular)
1. Abre una terminal y colócate en la carpeta del frontend:
   ```bash
   cd frontend
   ```
2. Instala las dependencias:
   ```bash
   npm install
   ```
3. Inicia el servidor de desarrollo:
   ```bash
   ng serve
   ```
   *La web estará disponible en `http://localhost:4200`*

### Levantando el Backend (PHP API)
1. Abre **otra** terminal y colócate en la carpeta del backend:
   ```bash
   cd backend
   ```
2. Inicia el servidor de desarrollo nativo de PHP:
   ```bash
   php -S localhost:8000
   ```
   *(Nota: Asegúrate de que MySQL esté encendido en tu panel de XAMPP para que la API logre conectarse a `lacasadeljean`).*

---
*Mantenido y orquestado bajo estructura DevOps - Monorepo.*
