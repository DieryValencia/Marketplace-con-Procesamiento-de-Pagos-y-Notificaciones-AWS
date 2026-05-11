import json
import boto3
import os
import uuid

# Inicializamos el cliente de SQS
sqs = boto3.client('sqs')
QUEUE_URL = os.environ.get('QUEUE_URL')

def lambda_handler(event, context):
    try:
        # 1. Extraer los datos del evento
        body = json.loads(event['body'])
        
        # Generar un Order ID para trazabilidad
        order_id = str(uuid.uuid4())
        body['orderId'] = order_id
        
        print(f"Procesando orden {order_id} para el producto: {body.get('producto', body.get('productId'))}")
        
        # 2. Enviar el mensaje a la cola SQS
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(body),
            MessageAttributes={
                'eventType': {
                    'DataType': 'String',
                    'StringValue': 'order.created'
                }
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Orden enviada a la cola', 'orderId': order_id, 'sqsMessageId': response['MessageId']})
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'No se pudo procesar la orden'})
        }