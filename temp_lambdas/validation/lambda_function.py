import boto3
import os

s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
sns = boto3.client('sns')

# Variables de entorno corregidas
MAX_SIZE_MB = 5
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:660880134439:marketplace-events-topic')

def lambda_handler(event, context):
    # 1. Obtener datos del evento
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key'] # Ej: uploads/foto.jpg
    file_name = os.path.basename(key)
    
    try:
        # 2. Validar Tamaño
        response = s3.head_object(Bucket=bucket, Key=key)
        size_mb = response['ContentLength'] / (1024 * 1024)
        
        if size_mb > MAX_SIZE_MB:
            reject_image(bucket, key, "El archivo supera los 5MB")
            return

        # 3. Llamar a Rekognition
        moderation_response = rekognition.detect_moderation_labels(
            Image={'S3Object': {'Bucket': bucket, 'Name': key}},
            MinConfidence=75
        )

        # 4. Verificar etiquetas de moderación
        if moderation_response['ModerationLabels']:
            labels = [label['Name'] for label in moderation_response['ModerationLabels']]
            reject_image(bucket, key, f"Contenido no apto detectado: {', '.join(labels)}")
        else:
            # Éxito: Mover a processed/
            copy_source = {'Bucket': bucket, 'Key': key}
            s3.copy_object(CopySource=copy_source, Bucket=bucket, Key=f"processed/{file_name}")
            s3.delete_object(Bucket=bucket, Key=key)
            print(f"Imagen {file_name} aprobada y movida a processed/")

    except Exception as e:
        print(f"Error procesando: {str(e)}")
        raise e

def reject_image(bucket, key, reason):
    file_name = os.path.basename(key)
    # Mover a rejected/
    copy_source = {'Bucket': bucket, 'Key': key}
    s3.copy_object(CopySource=copy_source, Bucket=bucket, Key=f"rejected/{file_name}")
    s3.delete_object(Bucket=bucket, Key=key)
    
    # Notificar por SNS
    message = f"Tu imagen {file_name} fue rechazada. Motivo: {reason}"
    sns.publish(TopicArn=SNS_TOPIC_ARN, Message=message, Subject="Imagen Rechazada - Marketplace")
    print(f"Imagen rechazada: {reason}")
