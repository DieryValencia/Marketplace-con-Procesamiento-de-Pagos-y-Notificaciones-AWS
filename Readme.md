# Marketplace con Procesamiento de Pagos y Notificaciones

Servicios: EC2 + ALB + Lambda + RDS + SQS + SNS + S3

Descripción: Vendedores publican productos (imágenes en S3, datos en RDS). Las órdenes entran por API Gateway → Lambda → SQS. Otra Lambda consume la cola, procesa el pago (simulado) y publica en SNS para notificar por email/SMS.

Implementar el patrón Fan-out: SNS tiene tres suscriptores distintos cuando llega una orden: (1) SQS cola de procesamiento de pago, (2) SQS cola de notificación al vendedor, (3) Lambda directa para actualizar inventario en RDS. Cada suscriptor debe tener un filter policy en SNS para recibir solo los mensajes que le corresponden según el tipo de evento.

 

La cola principal de SQS debe tener configurada una Dead Letter Queue (DLQ) con maxReceiveCount: 3. Una Lambda separada debe monitorear la DLQ cada 5 minutos via EventBridge, leer los mensajes fallidos, registrar el error en RDS y notificar al administrador por SNS.

 

EC2 con NGINX debe estar configurado como reverse proxy con upstream ponderado: 70% del tráfico al servidor de la app principal, 30% a una instancia "canary" con la versión nueva. Demostrar el cambio de pesos sin downtime.

 

Las imágenes de productos en S3 deben pasar por una Lambda de validación (tamaño máximo, formato permitido, sin contenido explícito usando Rekognition) antes de quedar disponibles. Si la validación falla, mover el objeto a un prefijo /rejected/ y notificar al vendedor.

## ALB Canary (implementado en AWS)

- **ALB:** `mybalanceadordecarga021` — DNS: `mybalanceadordecarga021-1004123642.us-east-1.elb.amazonaws.com`
- **Listener 80:** forward ponderado **70 %** `groupApp` (principal) / **30 %** `TG-Marketplace-Canary`
- **Instancias:** `Marketplace-Main` (`i-05fbee32a3ff873b5`) solo en `groupApp`; `Marketplace-Canary` (`i-0a6080416e7e70527`) solo en `TG-Marketplace-Canary`. Nginx en ambas responde **200** en `/` (cuerpo HTML distingue MAIN vs CANARY).
- **Nota:** la instancia antigua `EC2-NGINX-Proxy` (`i-0d7dfd5c6fef5eeda`) quedó fuera del balanceador (health check devolvía 500). Puedes detenerla o reconfigurarla si aún la necesitas fuera del ALB.
- **Coste:** dos `t3.micro` adicionales en ejecución; apágalas o elimínalas cuando no las uses.

**Probar distribución (200 peticiones, Bash):**

```bash
ALB_DNS="mybalanceadordecarga021-1004123642.us-east-1.elb.amazonaws.com"
main=0; canary=0
for i in $(seq 1 200); do
  body=$(curl -s --max-time 8 "http://${ALB_DNS}/")
  if echo "$body" | grep -q "Marketplace MAIN"; then ((main++)); elif echo "$body" | grep -q "Marketplace CANARY"; then ((canary++)); fi
done
echo "MAIN=$main CANARY=$canary"
```