import boto3
import json
import os
from datetime import datetime

# Nota: Requiere Layer con 'pymysql' para funcionar en AWS
try:
    import pymysql
except ImportError:
    pymysql = None

sqs = boto3.client('sqs')
sns = boto3.client('sns')

# Variables de entorno
DLQ_URL = os.environ.get('DLQ_URL')
SNS_ADMIN_TOPIC_ARN = os.environ.get('SNS_ADMIN_TOPIC_ARN')
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')

def lambda_handler(event, context):
    messages_processed = 0
    
    if not pymysql:
        print("ERROR: La librería 'pymysql' no está disponible. Debes agregar un Layer a la Lambda.")
        return {"status": "Error", "message": "Missing pymysql library"}

    try:
        # 1. Conectar a RDS (MySQL)
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            connect_timeout=5
        )
        cur = conn.cursor()

        while True:
            # 2. Leer mensajes de la DLQ
            response = sqs.receive_message(
                QueueUrl=DLQ_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1
            )

            if 'Messages' not in response:
                break

            for msg in response['Messages']:
                msg_id = msg['MessageId']
                body = msg['Body']
                
                # 3. Registrar el error en RDS
                insert_query = "INSERT INTO errores (source_queue, lambda_name, error_type, message, raw_payload) VALUES (%s, %s, %s, %s, %s)"
                cur.execute(insert_query, (
                    'marketplace-orders-main', 
                    'order-processor-handler', 
                    'DLQ_RETRY', 
                    'Mensaje fallido recuperado de DLQ', 
                    body
                ))
                
                # 4. Notificar al Administrador
                sns.publish(
                    TopicArn=SNS_ADMIN_TOPIC_ARN,
                    Message=f"ALERTA: Mensaje fallido en DLQ.\nID: {msg_id}\nContenido: {body}",
                    Subject="Error en Sistema de Órdenes"
                )

                # 5. Borrar el mensaje
                sqs.delete_message(QueueUrl=DLQ_URL, ReceiptHandle=msg['ReceiptHandle'])
                messages_processed += 1

        conn.commit()
        cur.close()
        conn.close()
        
        return {"status": "Success", "processed": messages_processed}

    except Exception as e:
        print(f"Error en monitor de DLQ: {str(e)}")
        raise e