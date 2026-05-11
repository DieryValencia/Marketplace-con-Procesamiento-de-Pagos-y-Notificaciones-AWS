# MarketAWS: E-commerce Serverless y Alta Disponibilidad

Este proyecto es un sistema de Marketplace robusto desplegado en AWS, utilizando una arquitectura moderna que combina servicios Serverless con infraestructura escalable.

## 🏗️ Arquitectura del Sistema

El sistema se divide en tres capas principales:

### 1. Capa de Usuario y Frontend
*   **Hosting:** Desplegado en **Amazon S3** como sitio web estático.
*   **Interfaz:** Diseño futurista "Nexus" con modo oscuro y acentos neon.
*   **Funcionalidad:** Permite navegar por productos y realizar compras simuladas conectándose directamente al backend.
*   **URL:** [http://marketplace-assets-prod-bucket.s3-website-us-east-1.amazonaws.com/](http://marketplace-assets-prod-bucket.s3-website-us-east-1.amazonaws.com/)

### 2. Procesamiento de Órdenes (Serverless)
*   **API Gateway:** Punto de entrada para las peticiones de compra.
*   **Lambda (Ingestion):** Recibe la orden, genera un ID único y la pone en una cola **SQS**.
*   **SQS (Main Queue):** Actúa como buffer para desacoplar la ingesta del procesamiento.
*   **Lambda (Processor):** Consume mensajes de SQS, simula el pago y publica en **SNS**.
*   **SNS (Fan-out):** Distribuye notificaciones a múltiples suscriptores (Email, Logs, etc.).
*   **Dead Letter Queue (DLQ):** Captura mensajes que fallan 3 veces para su posterior auditoría.

### 3. Infraestructura de Servidores (High Availability)
*   **Balanceador de Carga (ALB):** Distribuye el tráfico web.
*   **Despliegue Canary (70/30):** El ALB envía el 70% del tráfico a la versión estable (Main) y el 30% a la versión de prueba (Canary).
*   **EC2 Instances:** Servidores Nginx que alojan la lógica de servidor y el contenido.

---

## 🛠️ Credenciales y Endpoints Clave

*   **API URL:** `https://2uqkjsioug.execute-api.us-east-1.amazonaws.com/create-order`
*   **ALB DNS:** `mybalanceadordecarga021-1004123642.us-east-1.elb.amazonaws.com`
*   **RDS (MySQL):** `marketplace-prod-database-1.c8vy0soyszl7.us-east-1.rds.amazonaws.com`

---

## 🚀 Pruebas de Funcionamiento

### Crear una Orden (CURL / Postman)
```bash
curl -X POST https://2uqkjsioug.execute-api.us-east-1.amazonaws.com/create-order \
     -H "Content-Type: application/json" \
     -d '{"buyerId": "user_test", "productId": "101", "amount": 2500}'
```

### Verificar Balanceo Canary (PowerShell)
```powershell
for ($i=1; $i -le 20; $i++) { 
    $res = Invoke-RestMethod -Uri "http://mybalanceadordecarga021-1004123642.us-east-1.elb.amazonaws.com/"
    Write-Host "Petición $i: $res"
}
```

---

## 🛡️ Monitoreo y Fallos
Si un mensaje falla en la cola principal, se mueve a la **DLQ**. La Lambda `dlq-monitor-handler` se encarga de registrar estos fallos en la tabla `error_logs` de la base de datos MySQL para que el administrador pueda revisarlos.