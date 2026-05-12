import json
import pymysql
import boto3
import os

# DB Config
DB_HOST = "marketplace-prod-database-1.c8vy0soyszl7.us-east-1.rds.amazonaws.com"
DB_USER = "master_user"
DB_PASS = "OlKNhjLWfhh1lvI6o2s2"
DB_NAME = "marketplace-prod-database-1"

def get_db_conn():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def response(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body)
    }

def lambda_handler(event, context):
    print(f"Event received: {json.dumps(event)}")
    
    # Handle both REST API and HTTP API path formats
    path = event.get('path', event.get('rawPath', ''))
    method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method', ''))
    
    # Strip stage or /api prefix
    if path.startswith('/api'):
        path = path[4:]
    
    print(f"Normalized Path: {path}, Method: {method}")

    try:
        if method == "OPTIONS":
            return response(200, {"message": "CORS preflight successful"})

        if path == "/products" and method == "GET":
            print("Fetching products from RDS")
            conn = get_db_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM productos WHERE status = 'processed' LIMIT 50")
                rows = cur.fetchall()
            conn.close()
            return response(200, rows)

        elif path == "/get-upload-url" and method == "POST":
            print("Generating Presigned URL")
            body = json.loads(event.get('body', '{}'))
            file_name = body.get('fileName', 'image.jpg')
            s3 = boto3.client('s3')
            key = f"uploads/{file_name}"
            upload_url = s3.generate_presigned_url(
                ClientMethod='put_object',
                Params={'Bucket': 'marketplace-assets-prod-bucket', 'Key': key, 'ContentType': 'image/jpeg'},
                ExpiresIn=3600
            )
            return response(200, {'uploadUrl': upload_url, 'key': key})

        elif path.startswith("/order-status/") and method == "GET":
            order_id = path.split("/")[-1]
            conn = get_db_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM ordenes WHERE order_id = %s", (order_id,))
                order = cur.fetchone()
            conn.close()
            return response(200, order or {'status': 'pending'})

        elif path.startswith("/seller/status/") and method == "GET":
            file_name = path.split("/")[-1]
            conn = get_db_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM productos WHERE nombre = %s", (file_name,))
                row = cur.fetchone()
                status = row['status'] if row else "pending"
            conn.close()
            return response(200, {"status": status})

        elif path == "/admin/errors" and method == "GET":
            conn = get_db_conn()
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM errores ORDER BY created_at DESC LIMIT 50")
                errors = cur.fetchall()
            conn.close()
            return response(200, errors)

        return response(404, {"error": "Not Found", "path": path})

    except Exception as e:
        print(f"Internal Error: {str(e)}")
        return response(500, {"error": str(e)})
