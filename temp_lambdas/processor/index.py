import boto3
import json
import os
import random

sns = boto3.client('sns')
# CORREGIDO: ARN de SNS correcto
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:660880134439:marketplace-events-topic')

def lambda_handler(event, context):
    for record in event['Records']:
        try:
            # 1. Leer el cuerpo del mensaje de SQS
            order_data = json.loads(record['body'])
            order_id = order_data.get('orderId', 'unknown')
            
            print(f"Procesando orden: {order_id}")

            # 2. SIMULACIÓN DE PAGO
            payment_success = random.random() < 0.9
            
            if payment_success:
                event_type = "payment.succeeded"
                status_msg = "Pago aprobado"
            else:
                event_type = "payment.failed"
                status_msg = "Fondos insuficientes"

            # 3. Publicar resultado en SNS (Fan-out)
            message_attributes = {
                'eventType': {
                    'DataType': 'String',
                    'StringValue': event_type
                }
            }
            
            response_body = {
                'orderId': order_id,
                'status': status_msg,
                'customer_email': order_data.get('customer_email')
            }

            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=json.dumps(response_body),
                MessageAttributes=message_attributes,
                Subject=f"Resultado de Pago - {order_id}"
            )
            
            print(f"Resultado enviado a SNS: {event_type}")

        except Exception as e:
            print(f"Error procesando registro: {str(e)}")
            raise e